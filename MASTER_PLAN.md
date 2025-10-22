# 🎯 MASTER PLAN: Trustless Agent Economy
## Ecosistema de Agentes AI Autónomos con ERC-8004 + A2A + x402

> **Versión:** 1.0.0
> **Última actualización:** Octubre 2025
> **Estado:** 🚀 Phase 1 Complete - Smart Contracts Deployed

---

## 📍 Deployed Contracts (Avalanche Fuji Testnet)

| Contract | Address | Status |
|----------|---------|--------|
| **UVD V2 Token (EIP-3009)** | `0xfEe5CC33479E748f40F5F299Ff6494b23F88C425` | ✅ [Verified](https://testnet.snowtrace.io/address/0xfEe5CC33479E748f40F5F299Ff6494b23F88C425) |
| **Identity Registry (ERC-8004)** | `0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618` | ✅ [Verified](https://testnet.snowtrace.io/address/0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618) |
| **Reputation Registry (ERC-8004)** | `0x932d32194C7A47c0fe246C1d61caF244A4804C6a` | ✅ [Verified](https://testnet.snowtrace.io/address/0x932d32194C7A47c0fe246C1d61caF244A4804C6a) |
| **Validation Registry (ERC-8004)** | `0x9aF4590035C109859B4163fd8f2224b820d11bc2` | ✅ [Verified](https://testnet.snowtrace.io/address/0x9aF4590035C109859B4163fd8f2224b820d11bc2) |

**Deployment Date**: October 22, 2025
**Chain ID**: 43113 (Avalanche Fuji Testnet)
**Registration Fee**: 0.005 AVAX

---

## 📋 Tabla de Contenidos

1. [Visión General](#-visión-general)
2. [Arquitectura del Sistema](#-arquitectura-del-sistema)
3. [Componentes Principales](#-componentes-principales)
4. [Roadmap de Implementación](#-roadmap-de-implementación)
5. [Flujos de Trabajo](#-flujos-de-trabajo)
6. [Tecnologías y Protocolos](#-tecnologías-y-protocolos)
7. [Guías de Desarrollo](#-guías-de-desarrollo)
8. [Referencias](#-referencias)

---

## 🎯 Visión General

### Objetivo

Crear un **ecosistema completamente autónomo** donde agentes AI pueden:
- **Comercializar datos** de streaming (logs y transcripciones)
- **Realizar micropagos** sin gas fees usando x402 + EIP-3009
- **Construir reputación** on-chain con ERC-8004
- **Comunicarse** usando el protocolo A2A (Pydantic AI)
- **Validar transacciones** de forma trustless con agentes validadores

### Caso de Uso Principal

**Karma-Hello** (sistema de chat-to-earn) tiene logs de streams de Twitch.
**Abracadabra** (plataforma de transcripción) tiene transcripciones de audio.

**Problema**: Ambos sistemas tienen datos complementarios pero separados.

**Solución**: Crear agentes AI que negocien automáticamente la compra/venta de datos:
- Karma-Hello compra transcripciones → obtiene contexto completo
- Abracadabra compra logs → relaciona transcripciones con eventos del chat
- Validator verifica calidad antes de cada pago
- Todo on-chain en Fuji testnet con micropagos gasless

---

## 🏗️ Arquitectura del Sistema

### Diagrama de Alto Nivel

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FUJI TESTNET (AVALANCHE)                             │
│                                                                             │
│  ┌─────────────────┐  ┌──────────────────────────────────────────────┐    │
│  │   UVD V2 Token  │  │         ERC-8004 Registries                  │    │
│  │   (EIP-3009)    │  │                                              │    │
│  │                 │  │  ┌────────────┐ ┌────────────┐ ┌──────────┐ │    │
│  │  • transferWith │  │  │ Identity   │ │ Reputation │ │Validation│ │    │
│  │    Authorization│  │  │ Registry   │ │ Registry   │ │ Registry │ │    │
│  │  • Gasless txs  │  │  └────────────┘ └────────────┘ └─────┬────┘ │    │
│  └────────┬────────┘  └──────────┬─────────────────────────────┼──────┘    │
│           │                      │                             │           │
│           │                      │                  ❗VALIDATOR ESCRIBE❗  │
│           │                      │              validationResponse(...)    │
│           ▲                      ▲                             ▲           │
└───────────┼──────────────────────┼─────────────────────────────┼───────────┘
            │                      │                             │
            │ EIP-3009 Settlement  │ ERC-8004 Registration       │ Gas required!
            │                      │                             │
            │                      │                  ┌──────────┴──────────┐
            │                      │                  │ Validator Agent     │
            │                      │                  │ (Python + Web3)     │
            │                      │                  │                     │
            │                      │                  │ • Recibe requests   │
            │                      │                  │ • CrewAI analiza    │
            │                      │                  │ • PAGA GAS (~0.01   │
            │                      │                  │   AVAX) para tx     │
            │                      │                  │ • Cobra 0.001 UVD   │
            │                      │                  └──────────┬──────────┘
            │                      │                             │

┌─────────┴──────────────────────┴───────────────────────┴───────────┐
│          facilitator.ultravioletadao.xyz (x402-rs)                 │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  HTTP 402 Payment Required Handler                         │   │
│  │  • Verify EIP-712 signatures                               │   │
│  │  • Settle payments on-chain with transferWithAuthorization │   │
│  │  • Stateless verification                                  │   │
│  │  • Multi-chain support (Fuji primary)                      │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Endpoints:                                                         │
│  • POST /verify  - Verify payment payload                          │
│  • POST /settle  - Execute on-chain settlement                     │
│  • GET /supported - List supported payment methods                 │
└─────────────────────────────────────────────────────────────────────┘
          ▲                                            ▲
          │                                            │
          │  A2A Protocol (Pydantic AI)                │
          │  • AgentCard discovery                     │
          │  • Skill invocation                        │
          │  • Payment negotiation                     │
          │                                            │
┌─────────┴───────────────┐                 ┌─────────┴──────────────┐
│  Karma-Hello Agent      │                 │  Abracadabra Agent     │
│  System                 │                 │  System                │
│                         │                 │                        │
│  ┌──────────────────┐   │                 │  ┌──────────────────┐  │
│  │ KarmaHelloSeller │   │                 │  │AbracadabraSeller │  │
│  │  (Server Agent)  │   │                 │  │  (Server Agent)  │  │
│  │                  │   │                 │  │                  │  │
│  │ Sells:           │   │                 │  │ Sells:           │  │
│  │ • Stream logs    │   │                 │  │ • Transcripts    │  │
│  │ • Chat messages  │   │   Data Trade    │  │ • Topics         │  │
│  │ • Events         │   │◄────────────────►  │ • Segments       │  │
│  │ • User activity  │   │   (x402 HTTP)   │  │ • Timestamps     │  │
│  │                  │   │                 │  │                  │  │
│  │ API: /api/logs   │   │                 │  │ API: /api/trans  │  │
│  │ Price: 0.01 UVD  │   │                 │  │ Price: 0.02 UVD  │  │
│  │ ERC-8004: ID 1   │   │                 │  │ ERC-8004: ID 2   │  │
│  └──────────────────┘   │                 │  └──────────────────┘  │
│                         │                 │                        │
│  ┌──────────────────┐   │                 │  ┌──────────────────┐  │
│  │ KarmaHelloBuyer  │   │                 │  │ AbracadabraBuyer │  │
│  │  (Client Agent)  │   │                 │  │  (Client Agent)  │  │
│  │                  │   │                 │  │                  │  │
│  │ Buys:            │   │                 │  │ Buys:            │  │
│  │ • Transcripts    │   │                 │  │ • Stream logs    │  │
│  │   from Abracada  │   │                 │  │   from KarmaHello│  │
│  │                  │   │                 │  │                  │  │
│  │ Uses: x402-reqws │   │                 │  │ Uses: x402-reqws │  │
│  └──────────────────┘   │                 │  └──────────────────┘  │
│                         │                 │                        │
│  Data Source:           │                 │  Data Source:          │
│  z:\ultravioleta\ai\    │                 │  z:\ultravioleta\ai\   │
│     cursor\karma-hello  │                 │     cursor\abracadabra │
│                         │                 │                        │
└─────────────────────────┘                 └────────────────────────┘
```

### Stack Tecnológico

| Capa | Tecnología | Propósito |
|------|-----------|-----------|
| **Blockchain** | Avalanche Fuji Testnet | Red de pruebas para contratos |
| **Smart Contracts** | Solidity + Foundry | ERC-8004 Registries + UVD V2 Token |
| **Payment Protocol** | x402 (Rust) | HTTP micropagos con 402 status code |
| **Agent Protocol** | A2A (Pydantic AI) | Comunicación agente-a-agente |
| **AI Orchestration** | CrewAI | Multi-agent workflows |
| **Agent Backend** | Python 3.11+ | Lógica de agentes |
| **Payment Middleware** | Axum (Rust) | Server-side x402 |
| **Payment Client** | reqwest (Rust) | Client-side x402 |
| **Token Standard** | ERC-20 + EIP-3009 | Gasless transfers |

---

## 🧩 Componentes Principales

### 1. UVD V2 Token (`erc-20/`)

**Objetivo**: Token ERC-20 con soporte de meta-transacciones para pagos gasless.

**Estado**: ✅ Implementado, listo para deployment

**Deployment Parameters (Matching UVT V1):**
- Initial Supply: 24,157,817 UVD
- Owner: 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8
- Decimals: 6 (matching USDC)
- Network: Avalanche Fuji (Chain ID: 43113)

**Features**:
- ✅ ERC-20 estándar compliance
- ✅ EIP-3009: `transferWithAuthorization()` (core feature for x402)
- ✅ EIP-2612: `permit()` para gasless approvals
- ✅ EIP-712: Typed structured data hashing
- ✅ Nonce-based replay protection
- ✅ Time-window validation (validAfter/validBefore)
- ✅ Cancel authorization capability
- ✅ Integración con x402 facilitator

**Estructura de Archivos**:
```
erc-20/
├── src/
│   └── UVD_V2.sol           ← Contrato principal (214 líneas)
├── script/
│   └── Deploy.s.sol         ← Foundry deployment script
├── foundry.toml             ← Configuración para Fuji
├── deploy-fuji.sh           ← Script automatizado de deployment
├── .env.example             ← Template con valores de UVT V1
├── .gitignore               ← Protección de artifacts
└── README.md                ← Guía completa de deployment
```

**Deployment Rápido**:
```bash
cd erc-20
cp .env.example .env && nano .env    # Configurar PRIVATE_KEY
forge install                        # Instalar dependencias
./deploy-fuji.sh                     # Deploy a Fuji
```

**Output**: `deployment.json` con token address para x402

---

### 2. ERC-8004 Registries (`erc-8004/`)

**Objetivo**: Registros on-chain de identidad, reputación y validación de agentes.

**Contratos**:
- `IdentityRegistry.sol` - Registro de agentes con dominios
- `ReputationRegistry.sol` - Sistema de feedback y ratings
- `ValidationRegistry.sol` - Validaciones y scores

**Estado**: ✅ Ya extraído, listo para desplegar

**Archivos**:
```
erc-8004/
├── README.md
├── contracts/
│   ├── src/
│   │   ├── IdentityRegistry.sol
│   │   ├── ReputationRegistry.sol
│   │   └── ValidationRegistry.sol
│   ├── script/
│   │   └── Deploy.s.sol
│   └── foundry.toml
├── deploy-fuji.sh
├── deploy-fuji.ps1
├── deploy-fuji.bat
├── .env.fuji.example
└── DEPLOY-FUJI.md
```

---

### 3. x402 Facilitator (`x402-rs/`)

**Objetivo**: Servidor HTTP que facilita pagos x402 en Fuji.

**URL Pública**: `https://facilitator.ultravioletadao.xyz`

**Features**:
- ✅ Verifica firmas EIP-712
- ✅ Ejecuta `transferWithAuthorization` on-chain
- ✅ Stateless (no DB, todo on-chain)
- ✅ Multi-token support (UVD, USDC, WAVAX)
- ✅ OpenTelemetry tracing (Prometheus + Grafana + Loki)
- ✅ HTTPS con Caddy reverse proxy
- ✅ Rate limiting (60 req/min)
- ✅ Hot wallet rotation strategy

**Endpoints**:
```
POST /verify   - Verifica payload de pago
POST /settle   - Ejecuta transferencia on-chain
GET /supported - Lista métodos de pago soportados
GET /health    - Health check
GET /metrics   - Prometheus metrics
```

**Estado**: ⏸️ **TEMPORAL: Using External Facilitator**

> **NOTA IMPORTANTE**: El facilitador x402-rs requiere Rust edition 2024 (nightly).
> Por ahora, usaremos un facilitador externo existente para testing.
> El código está listo y será desplegado cuando se actualice a Rust stable edition 2021.
>
> **Alternativa actual**: Usar facilitador público o implementar verificación directa en agentes

**Estructura de Archivos**:
```
x402-rs/
├── src/
│   └── network.rs           ← UVD + WAVAX tokens agregados
├── .env.example             ← Configuración completa para Fuji
├── Caddyfile                ← HTTPS reverse proxy
├── docker-compose.yml       ← Multi-service deployment
├── prometheus.yml           ← Metrics collection
├── deploy-facilitator.sh    ← Automated deployment script
├── DEPLOYMENT.md            ← Step-by-step deployment guide
└── README.md                ← Karmacadabra-specific docs
```

**Configuración Completa** (ver `.env.example`):
```bash
# Network
SIGNER_TYPE=private-key
EVM_PRIVATE_KEY=0x...                        # Hot wallet (2-5 AVAX for gas)
RPC_URL_AVALANCHE_FUJI=https://your-rpc.xyz  # Custom RPC
RPC_URL_AVALANCHE_FUJI_FALLBACK=https://avalanche-fuji-c-chain-rpc.publicnode.com
CHAIN_ID=43113

# Server
HOST=0.0.0.0
PORT=8080
RUST_LOG=info

# Tokens (Avalanche Fuji)
UVD_TOKEN_ADDRESS=0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618  # ✅ DEPLOYED
USDC_FUJI_ADDRESS=0x5425890298aed601595a70AB815c96711a31Bc65
WAVAX_FUJI_ADDRESS=0xd00ae08403B9bbb9124bB305C09058E32C39A48c

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://grafana.ultravioletadao.xyz:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_SERVICE_NAME=x402-facilitator-karmacadabra

# Rate Limiting
RATE_LIMIT_ENABLED=false  # Enable in production
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# Hot Wallet Management
BALANCE_ALERT_THRESHOLD=1.0
STANDBY_WALLET_ADDRESS=0x...  # For monthly rotation
```

**Deployment Rápido**:
```bash
# 1. Initialize
cd x402-rs
./deploy-facilitator.sh init

# 2. Configure .env (update UVD_TOKEN_ADDRESS after erc-20 deployment)
cp .env.example .env
nano .env

# 3. Build & Deploy
./deploy-facilitator.sh build
./deploy-facilitator.sh deploy

# 4. Verify
./deploy-facilitator.sh status
curl https://facilitator.ultravioletadao.xyz/health
curl https://facilitator.ultravioletadao.xyz/supported
```

**Infraestructura**:
- **Deployment**: Docker on Cherry Servers
- **HTTPS**: Caddy with auto SSL (Let's Encrypt)
- **Monitoring**: Prometheus + Grafana dashboards
- **Logs**: JSON format, rotated daily
- **Backup**: Automated daily backups

**Guía Completa**: Ver `x402-rs/DEPLOYMENT.md` para deployment paso a paso

---

### 4. Karma-Hello Agent System (`karma-hello-agent/`)

**Objetivo**: Agentes que comercializan logs de streams de Twitch.

#### 4.1 KarmaHelloSeller (Server Agent)

**Rol**: Vende logs de streams de Twitch

**Datos que vende**:
- Chat messages con timestamps
- User activity (joins, parts, subscriptions)
- Token rewards distribuidos
- Stream events (raids, host, etc.)
- Metadata de usuarios (badges, colors)

**API Endpoint**: `POST /api/logs`

**Precio**: 0.01 UVD por query

**Implementación**:
```python
# Base en CrewAI + A2A
class KarmaHelloSeller(ERC8004BaseAgent, A2AServer):
    def __init__(self):
        # Conexión a MongoDB con logs
        self.db = MongoClient(...)["karma_hello"]

        # Registro ERC-8004
        self.register_agent(domain="karma-hello-seller.ultravioletadao.xyz")

        # A2A Skills
        self.register_skill("get_logs", self.get_logs_handler)

    @x402_required(price=UVD.amount("0.01"))
    async def get_logs_handler(self, request: LogsRequest):
        # CrewAI crew para formatear logs
        crew = Crew(
            agents=[self.data_formatter, self.quality_checker],
            tasks=[format_task, quality_task]
        )

        result = crew.kickoff()
        return LogsResponse(data=result)
```

#### 4.2 KarmaHelloBuyer (Client Agent)

**Rol**: Compra transcripciones de Abracadabra

**Lógica**:
1. Detecta que falta contexto de audio en logs
2. Descubre Abracadabra agent via A2A
3. Negocia precio
4. Firma EIP-712 authorization
5. Envía request con `X-Payment` header
6. Integra transcripción con logs existentes

**Implementación**:
```python
class KarmaHelloBuyer(ERC8004BaseAgent, A2AClient):
    def __init__(self):
        self.a2a_client = A2AHttpClient()
        self.payment_signer = EIP712Signer(private_key=...)

    async def buy_transcript(self, stream_id: str):
        # Discover Abracadabra seller
        agent_card = await self.a2a_client.discover(
            "abracadabra-seller.ultravioletadao.xyz"
        )

        # Get price from AgentCard
        skill = agent_card.skills["get_transcript"]
        price = skill.price  # 0.02 UVD

        # Sign EIP-712 payment
        auth = self.payment_signer.sign_transfer_authorization(
            from_=self.address,
            to=agent_card.payment_address,
            value=price.to_token_amount(),
            valid_after=0,
            valid_before=now() + 3600,
            nonce=random_nonce()
        )

        # Make request with payment
        response = await self.a2a_client.invoke_skill(
            agent_card,
            "get_transcript",
            params={"stream_id": stream_id},
            payment=auth
        )

        # Store in DB
        self.db.transcripts.insert_one(response.data)
```

**Estado**: 🔴 Por crear

**Archivos**:
```
karma-hello-agent/
├── README.md
├── SETUP.md
├── API.md
├── agents/
│   ├── __init__.py
│   ├── base_agent.py           # ERC-8004 + A2A base
│   ├── karma_hello_seller.py   # Server agent
│   ├── karma_hello_buyer.py    # Client agent
│   └── tools.py                # CrewAI tools
├── config.yaml
├── .env.example
├── requirements.txt
├── main.py                     # Entry point
└── tests/
```

---

### 5. Abracadabra Agent System (`abracadabra-agent/`)

**Objetivo**: Agentes que comercializan transcripciones de streams.

#### 5.1 AbracadabraSeller (Server Agent)

**Rol**: Vende transcripciones de audio/video

**Datos que vende**:
- Transcripciones completas (AWS Transcribe + Whisper)
- Segmentos con timestamps
- Topics extraídos con GPT-4o
- Entidades mencionadas (personas, lugares, productos)
- Sentiment analysis
- Keywords y quotes destacados

**API Endpoint**: `POST /api/transcripts`

**Precio**: 0.02 UVD por transcripción

**Fuente de datos**: Base de datos SQLite + Cognee knowledge graph

**Implementación**:
```python
class AbracadabraSeller(ERC8004BaseAgent, A2AServer):
    def __init__(self):
        # Conexión a analytics.db (SQLite)
        self.db = sqlite3.connect("analytics.db")

        # Cognee para búsqueda semántica
        self.cognee = CogneeClient()

        # Registro ERC-8004
        self.register_agent(domain="abracadabra-seller.ultravioletadao.xyz")

        # A2A Skills
        self.register_skill("get_transcript", self.get_transcript_handler)
        self.register_skill("search_topics", self.search_topics_handler)

    @x402_required(price=UVD.amount("0.02"))
    async def get_transcript_handler(self, request: TranscriptRequest):
        # CrewAI crew para enriquecer transcripción
        crew = Crew(
            agents=[self.data_enricher, self.topic_analyzer],
            tasks=[enrich_task, analyze_task]
        )

        # Buscar transcripción en DB
        transcript = self.db.execute(
            "SELECT * FROM transcripts WHERE stream_id = ?",
            (request.stream_id,)
        ).fetchone()

        # Enriquecer con Cognee
        topics = await self.cognee.search(transcript.text)

        result = crew.kickoff(inputs={
            "transcript": transcript,
            "topics": topics
        })

        return TranscriptResponse(data=result)
```

#### 5.2 AbracadabraBuyer (Client Agent)

**Rol**: Compra logs de Karma-Hello

**Lógica**:
1. Detecta menciones en transcripción sin contexto del chat
2. Descubre Karma-Hello agent via A2A
3. Compra logs del mismo timestamp
4. Relaciona transcripción con eventos del chat
5. Enriquece knowledge graph de Cognee

**Estado**: 🔴 Por crear

**Archivos**:
```
abracadabra-agent/
├── README.md
├── SETUP.md
├── API.md
├── agents/
│   ├── __init__.py
│   ├── base_agent.py              # ERC-8004 + A2A base
│   ├── abracadabra_seller.py      # Server agent
│   ├── abracadabra_buyer.py       # Client agent
│   └── tools.py                   # CrewAI tools
├── config.yaml
├── .env.example
├── requirements.txt
├── main.py
└── tests/
```

---

### 6. Validator Agent (`validator/`)

**Objetivo**: Agente independiente que valida la calidad de datos antes de cada transacción.

**Basado en**: Bob del ejemplo ERC-8004

**Rol**: Validador neutral que recibe fee por validación

**Lógica de validación**:

```python
class ValidatorAgent(ERC8004BaseAgent):
    def __init__(self):
        # Registro como validador
        self.register_agent(domain="validator.ultravioletadao.xyz")

        # CrewAI crew para validación
        self.validator_crew = Crew(
            agents=[
                self.quality_analyst,    # Analiza calidad de datos
                self.price_reviewer,     # Verifica que precio es justo
                self.fraud_detector      # Detecta datos duplicados/fake
            ],
            tasks=[quality_task, price_task, fraud_task]
        )

    async def validate_transaction(self,
                                  data_hash: str,
                                  seller_id: int,
                                  buyer_id: int) -> ValidationResult:
        # Cargar datos a validar
        data = await self.load_data(data_hash)

        # Ejecutar crew de validación
        validation_report = self.validator_crew.kickoff(inputs={
            "data": data,
            "seller": seller_id,
            "buyer": buyer_id
        })

        # Extraer score (0-100)
        score = self.extract_score(validation_report)

        # Subir validación on-chain
        tx = await self.submit_validation_response(
            data_hash=bytes.fromhex(data_hash),
            response=score
        )

        return ValidationResult(
            score=score,
            report=validation_report,
            tx_hash=tx
        )
```

**Criterios de validación**:

Para **Logs** (Karma-Hello):
- ✅ Timestamps son válidos
- ✅ User IDs existen en Twitch
- ✅ Mensajes tienen contenido (no vacíos)
- ✅ No hay duplicados
- ✅ Formato JSON es válido

Para **Transcripciones** (Abracadabra):
- ✅ Audio/video realmente existe
- ✅ Transcripción tiene coherencia
- ✅ Timestamps coinciden con duración del stream
- ✅ No es texto generado random
- ✅ Topics son relevantes

**Fees**:
- 0.001 UVD por validación (pagado por el comprador)
- Reputación on-chain basada en accuracy de validaciones

**Estado**: 🔴 Por crear

**Archivos**:
```
validator/
├── README.md
├── SETUP.md
├── agents/
│   ├── __init__.py
│   ├── base_agent.py       # Hereda de ERC8004BaseAgent
│   ├── validator_agent.py  # Lógica principal (basada en Bob)
│   └── validation_tools.py # Tools de CrewAI
├── config.yaml
├── .env.example
├── requirements.txt
├── main.py
└── tests/
```

---

## 🗺️ Roadmap de Implementación

### Phase 1: Infraestructura Blockchain (Semana 1-2)

**Objetivo**: Desplegar toda la infraestructura on-chain en Fuji.

#### Milestone 1.1: UVD V2 Token
- [x] Crear contrato `UVD_V2.sol` con EIP-3009
- [x] Implementar transferWithAuthorization (gasless transfers)
- [x] Implementar cancelAuthorization (replay protection)
- [x] Agregar EIP-2612 Permit (gasless approvals)
- [x] Agregar EIP-712 typed data hashing
- [x] Crear Foundry deployment script (Deploy.s.sol)
- [x] Crear foundry.toml configuración para Fuji
- [x] Crear deploy-fuji.sh script automatizado
- [x] Configurar .env.example con valores de UVT V1
- [x] Actualizar README.md con deployment steps
- [ ] Deploy a Avalanche Fuji Testnet
- [ ] Verificar en Snowtrace
- [ ] Guardar address en deployment.json
- [ ] Distribuir tokens iniciales si necesario

**Deployment Parameters (Matching UVT V1):**
- **Initial Supply**: 24,157,817 UVD
- **Owner Wallet**: 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8
- **Decimals**: 6 (matching USDC for lower gas)
- **Total Supply**: 24,157,817,000,000 (with decimals)
- **Network**: Avalanche Fuji (Chain ID: 43113)

**Contract Features:**
- ✅ ERC-20 standard compliance
- ✅ EIP-3009 transferWithAuthorization (core feature for x402)
- ✅ EIP-2612 Permit (gasless approvals)
- ✅ EIP-712 typed structured data
- ✅ Nonce-based replay protection
- ✅ Time-window validation (validAfter/validBefore)
- ✅ Cancel authorization capability

**Deployment Commands:**
```bash
cd erc-20
cp .env.example .env && nano .env  # Configure PRIVATE_KEY & RPC_URL
forge install                      # Install dependencies
./deploy-fuji.sh                   # Deploy to Fuji
```

**Output:** `deployment.json` with token address for x402 configuration

**Entregables**:
- ✅ Contrato UVD_V2.sol completo (214 líneas)
- ✅ Deployment script automatizado (deploy-fuji.sh)
- ✅ Foundry configuration (foundry.toml)
- ✅ Deploy script (script/Deploy.s.sol)
- ✅ .env.example con parámetros de UVT V1
- ✅ README.md actualizado con deployment steps
- ⏳ Deployment a Fuji (pending execution)
- ⏳ ABI exportado (after deployment)
- ⏳ Tokens en owner wallet (minted on deployment)

#### Milestone 1.2: ERC-8004 Registries
- [ ] Desplegar IdentityRegistry en Fuji
- [ ] Desplegar ReputationRegistry en Fuji
- [ ] Desplegar ValidationRegistry en Fuji
- [ ] Verificar contratos en Snowtrace
- [ ] Testing de registro de agentes
- [ ] Documentar deployment.json

**Entregables**:
- ✅ 3 contratos desplegados
- ✅ deployment.json con addresses
- ✅ Guía de uso

#### Milestone 1.3: x402 Facilitator
- [x] Configurar x402-rs para Fuji
- [x] Agregar UVD V2 token a network.rs
- [x] Agregar WAVAX token a network.rs
- [x] Crear .env.example con configuración completa
- [x] Crear Caddyfile para HTTPS reverse proxy
- [x] Crear docker-compose.yml para deployment
- [x] Crear prometheus.yml para metrics
- [x] Crear deploy-facilitator.sh script
- [x] Crear DEPLOYMENT.md guía completa
- [ ] Deploy UVD V2 token (prerequisito)
- [ ] Actualizar UVD_TOKEN_ADDRESS en .env
- [ ] Generar hot wallet y fundar con AVAX
- [ ] Deploy a facilitator.ultravioletadao.xyz con Docker
- [ ] Configurar Caddy HTTPS
- [ ] Testing de /health endpoint
- [ ] Testing de /supported endpoint
- [ ] Testing de /verify endpoint
- [ ] Testing de /settle endpoint
- [ ] Configurar Prometheus + Grafana dashboards
- [ ] Setup alertas (balance < 1 AVAX, high error rate)

**Herramientas de Deployment**:
```bash
./deploy-facilitator.sh init     # Initialize deployment
./deploy-facilitator.sh build    # Build Docker image
./deploy-facilitator.sh deploy   # Deploy with Docker Compose
./deploy-facilitator.sh status   # Check health
./deploy-facilitator.sh logs     # View logs
```

**Entregables**:
- ✅ Configuración completa en x402-rs/
- ✅ .env.example con todas las variables
- ✅ Caddyfile para HTTPS
- ✅ docker-compose.yml multi-service
- ✅ prometheus.yml para metrics
- ✅ deploy-facilitator.sh automation
- ✅ DEPLOYMENT.md paso a paso
- ⏳ Facilitator corriendo en producción (pending UVD deployment)
- ⏳ HTTPS configurado (pending DNS + deployment)
- ✅ Documentación de API (en README.md)

---

### Phase 2: Agentes Base (Semana 3)

**Objetivo**: Crear la arquitectura base de agentes con ERC-8004 + A2A.

#### Milestone 2.1: Base Agent Architecture
- [ ] Crear `base_agent.py` con ERC-8004 integration
- [ ] Implementar A2A protocol client/server
- [ ] Agregar EIP-712 signing para pagos
- [ ] CrewAI base setup
- [ ] Testing de registro en contratos
- [ ] Documentar API de base_agent

**Entregables**:
- ✅ `base_agent.py` reutilizable
- ✅ Tests unitarios
- ✅ Ejemplos de uso

#### Milestone 2.2: Validator Agent
- [ ] Extraer lógica de Bob → validator_agent.py
- [ ] Implementar CrewAI crews de validación
- [ ] Integrar con ValidationRegistry
- [ ] Testing con datos mock
- [ ] Documentar criterios de validación

**Entregables**:
- ✅ Validator agent funcional
- ✅ Validación de logs y transcripts
- ✅ Reportes de validación

---

### Phase 3: Karma-Hello Agents (Semana 4)

**Objetivo**: Agentes que comercializan logs de streams.

**Nota**: Ver `MONETIZATION_OPPORTUNITIES.md` para catálogo completo de servicios (50+ productos, Tiers 1-6).

#### Milestone 3.1: KarmaHelloSeller
- [ ] Implementar `karma_hello_seller.py`
- [ ] API REST con Axum + x402-axum middleware
- [ ] Integración con MongoDB de karma-hello
- [ ] CrewAI crew para formateo de logs
- [ ] A2A AgentCard publicación
- [ ] Testing end-to-end
- [ ] **Implementar servicios Tier 1-2** (Chat logs, User activity, Token economics - ver MONETIZATION)

**Entregables**:
- ✅ API corriendo en servidor
- ✅ Endpoint /api/logs con x402
- ✅ Documentación de API
- ✅ Servicios básicos monetizables (0.01-0.15 UVD)

#### Milestone 3.2: KarmaHelloBuyer
- [ ] Implementar `karma_hello_buyer.py`
- [ ] Cliente A2A para discovery
- [ ] Integración con x402-reqwest
- [ ] Lógica de compra automática
- [ ] Testing con Abracadabra mock

**Entregables**:
- ✅ Buyer agent funcional
- ✅ Compras automáticas
- ✅ Integración de datos

---

### Phase 4: Abracadabra Agents (Semana 5)

**Objetivo**: Agentes que comercializan transcripciones.

**Nota**: Ver `MONETIZATION_OPPORTUNITIES.md` para catálogo completo de servicios (50+ productos, Tiers 1-6).

#### Milestone 4.1: AbracadabraSeller
- [ ] Implementar `abracadabra_seller.py`
- [ ] API REST con Axum + x402-axum
- [ ] Integración con analytics.db (SQLite)
- [ ] Integración con Cognee
- [ ] CrewAI crew para enriquecimiento
- [ ] A2A AgentCard publicación
- [ ] Testing end-to-end
- [ ] **Implementar servicios Tier 1-2** (Raw transcripts, Enhanced, Topics - ver MONETIZATION)

**Entregables**:
- ✅ API corriendo
- ✅ Endpoint /api/transcripts con x402
- ✅ Búsqueda semántica funcional
- ✅ Servicios básicos monetizables (0.02-0.25 UVD)

#### Milestone 4.2: AbracadabraBuyer
- [ ] Implementar `abracadabra_buyer.py`
- [ ] Cliente A2A
- [ ] Lógica de compra automática
- [ ] Enriquecimiento de knowledge graph
- [ ] Testing con Karma-Hello mock

**Entregables**:
- ✅ Buyer agent funcional
- ✅ Integración completa

---

### Phase 5: Integración y Testing (Semana 6)

**Objetivo**: Integrar todos los componentes y testing exhaustivo.

#### Milestone 5.1: Flujo Completo
- [ ] Testing Karma-Hello → Validator → Abracadabra
- [ ] Testing Abracadabra → Validator → Karma-Hello
- [ ] Verificar pagos on-chain
- [ ] Verificar reputación on-chain
- [ ] Load testing

**Entregables**:
- ✅ Flujo end-to-end funcional
- ✅ Métricas de performance

#### Milestone 5.2: Demo Script
- [ ] Crear `demo.py` como el original
- [ ] Registrar todos los agentes
- [ ] Simular compra/venta automática
- [ ] Display audit trail
- [ ] Video demo

**Entregables**:
- ✅ Demo script ejecutable
- ✅ Video tutorial
- ✅ Documentación completa

---

## 🔄 Flujos de Trabajo

### Flujo 1: Karma-Hello compra Transcripción de Abracadabra

```
┌──────────────┐
│ KarmaHello   │
│ Buyer Agent  │
└──────┬───────┘
       │ 1. Detecta necesidad de transcripción para stream_id=12345
       │
       ▼
┌──────────────────────────────────────┐
│ A2A Discovery                        │
│ GET /.well-known/agent-card          │
│ Host: abracadabra-seller.ultravioleta│
└──────┬───────────────────────────────┘
       │ 2. Recibe AgentCard con skills y precios
       │
       ▼
┌──────────────────────────────────────┐
│ EIP-712 Signing                      │
│ - from: KarmaHello wallet            │
│ - to: Abracadabra wallet             │
│ - value: 20000 (0.02 UVD, 6 decimals)│
│ - nonce: random                      │
│ - validAfter: 0                      │
│ - validBefore: now + 1h              │
└──────┬───────────────────────────────┘
       │ 3. Firma con private key
       │
       ▼
┌──────────────────────────────────────┐
│ HTTP Request con Payment             │
│ POST /api/transcripts                │
│ X-Payment: {                         │
│   "kind": "evm-eip3009-USDC",        │
│   "payload": {                       │
│     "from": "0x...",                 │
│     "to": "0x...",                   │
│     "value": "20000",                │
│     "validAfter": "0",               │
│     "validBefore": "1234567890",     │
│     "nonce": "0xabc...",             │
│     "v": 27,                         │
│     "r": "0x...",                    │
│     "s": "0x..."                     │
│   }                                  │
│ }                                    │
│ Body: {"stream_id": "12345"}         │
└──────┬───────────────────────────────┘
       │ 4. Enviado a Abracadabra
       │
       ▼
┌──────────────────────────────────────┐
│ Abracadabra Seller                   │
│ x402-axum middleware intercepta      │
└──────┬───────────────────────────────┘
       │ 5. Extrae X-Payment header
       │
       ▼
┌──────────────────────────────────────┐
│ Facilitator Verify                   │
│ POST https://facilitator.ultravioleta│
│      dao.xyz/verify                  │
└──────┬───────────────────────────────┘
       │ 6. Verifica firma EIP-712
       │    Verifica balance de KarmaHello
       │    Verifica nonce no usado
       │
       ▼
┌──────────────────────────────────────┐
│ Request Validation (Optional)        │
│ ERC-8004 ValidationRegistry          │
└──────┬───────────────────────────────┘
       │ 7. Abracadabra solicita validación (ON-CHAIN)
       │    validationRequest(validator_id,
       │                       abracadabra_id,
       │                       data_hash)
       │    📝 Escribe en blockchain
       │
       ▼
┌──────────────────────────────────────┐
│ Validator Agent (Python + Web3.py)  │
│ - Escucha events ValidationRequest  │
│ - Paga 0.001 UVD al validator        │
│ - Descarga transcripción             │
│ - CrewAI valida calidad (GPT-4o)     │
│ - 🔴 PAGA GAS (~0.01 AVAX) 🔴        │
│ - Submite score ON-CHAIN             │
└──────┬───────────────────────────────┘
       │ 8. ValidationResponse(score=95) - ON-CHAIN TX
       │    validationResponse(dataHash, 95)
       │    ⛽ Gas pagado por VALIDATOR_WALLET
       │    📝 Score guardado en blockchain
       │    📡 Event emitido: ValidationResponseEvent
       │
       ▼
┌──────────────────────────────────────┐
│ Facilitator Settle                   │
│ POST /settle                         │
│ Ejecuta: transferWithAuthorization() │
│ en UVD V2 contract                   │
└──────┬───────────────────────────────┘
       │ 9. Tokens transferidos
       │    KarmaHello -0.02 UVD
       │    Abracadabra +0.02 UVD
       │
       ▼
┌──────────────────────────────────────┐
│ Abracadabra Seller                   │
│ Handler ejecuta:                     │
│ - Busca transcripción en DB          │
│ - Enriquece con Cognee               │
│ - CrewAI formatea respuesta          │
│ - Retorna JSON                       │
└──────┬───────────────────────────────┘
       │ 10. Response 200 OK
       │     { transcript: {...} }
       │
       ▼
┌──────────────────────────────────────┐
│ KarmaHello Buyer                     │
│ - Recibe transcripción               │
│ - Integra con logs en MongoDB        │
│ - Actualiza knowledge base           │
└──────────────────────────────────────┘
```

**Duración total**: ~2-3 segundos (sin validación) / ~5-7 segundos (con validación)

**Costos de Gas (AVAX)**:
- ✅ Buyer: 0 (gasless gracias a EIP-3009)
- ✅ Seller: 0 (gasless gracias a EIP-3009)
- ✅ Facilitator: 0 (stateless, solo verifica firmas off-chain)
- 🔴 **Validator: ~0.01 AVAX** (paga gas por tx `validationResponse()` on-chain)

**Fees en UVD**:
- Abracadabra Seller: +0.02 UVD (recibe pago)
- Facilitator: 0 UVD (no cobra fee actualmente)
- Validator: +0.001 UVD (recibe fee, pero paga 0.01 AVAX gas - no rentable en testnet)
- Karma-Hello Buyer: -0.021 UVD total (-0.02 seller, -0.001 validator)

**⚠️ Nota Importante**: La economía del Validator no es sostenible con fee de 0.001 UVD ya que paga ~0.01 AVAX por transacción. En producción considerar:
- Aumentar `VALIDATION_FEE_UVD` a 0.01+ UVD
- Usar Layer 2 / Optimistic Rollup para reducir gas
- Batch validations (validar múltiples items en una tx)

---

### Flujo 2: Abracadabra compra Logs de Karma-Hello

```
[Similar al Flujo 1 pero invertido]

1. AbracadabraBuyer detecta mención en transcript sin contexto
2. A2A Discovery de KarmaHelloSeller
3. Firma EIP-712 authorization (0.01 UVD)
4. POST /api/logs con X-Payment header
5. Facilitator verifica
6. Validator valida (opcional)
7. Facilitator settle
8. KarmaHelloSeller retorna logs
9. Abracadabra enriquece knowledge graph
```

---

## 🔧 Tecnologías y Protocolos

### ERC-8004: Trust Frameworks for AI Agents

**Spec**: https://eips.ethereum.org/EIPS/eip-8004

**Componentes**:

1. **IdentityRegistry**
   - `newAgent(domain, agentAddress)` → agentId
   - `resolveByAddress(address)` → agentInfo
   - `resolveByDomain(domain)` → agentInfo

2. **ReputationRegistry**
   - `acceptFeedback(fromAgent, toAgent)`
   - `rateClient(clientAgent, rating)`
   - `getReputation(agentId)` → score

3. **ValidationRegistry** 🔴 **REQUIERE GAS** 🔴
   - `validationRequest(validator, requester, dataHash)` - Buyer llama (puede ser gasless via relayer)
   - `validationResponse(dataHash, score)` - **❗Validator PAGA GAS❗** (~0.01 AVAX)
   - `rateValidator(validatorId, rating)` - Feedback del seller
   - `getValidationResponse(dataHash)` - Leer score (gratis)

**Uso en nuestro sistema**:
- Cada agente (seller, buyer, validator) se registra con ID único en `IdentityRegistry`
- Reputación se construye en cada transacción en `ReputationRegistry`
- **Validaciones quedan registradas on-chain en `ValidationRegistry`**
- Validator es el **ÚNICO agente que paga gas** (los demás usan EIP-3009 gasless)
- Ratings bidireccionales: seller ← → buyer, buyer → validator

---

### A2A Protocol (Agent-to-Agent)

**Spec**: https://ai.pydantic.dev/a2a/

**Componentes clave**:

1. **AgentCard** (Discovery)
```json
{
  "agentId": 1,
  "name": "Karma-Hello Seller",
  "description": "Sells Twitch stream logs",
  "version": "1.0.0",
  "skills": [
    {
      "skillId": "get_logs",
      "name": "Get Stream Logs",
      "description": "Retrieve chat logs for a stream",
      "price": {
        "amount": "0.01",
        "currency": "UVD"
      },
      "inputSchema": {
        "type": "object",
        "properties": {
          "stream_id": {"type": "string"},
          "start_time": {"type": "integer"},
          "end_time": {"type": "integer"}
        }
      },
      "outputSchema": {
        "type": "object",
        "properties": {
          "logs": {"type": "array"}
        }
      }
    }
  ],
  "trustModels": ["erc-8004"],
  "paymentMethods": ["x402-eip3009"]
}
```

2. **Skill Invocation**
```python
# Discovery
agent_card = await a2a_client.get_agent_card(
    "https://karma-hello-seller.ultravioletadao.xyz/.well-known/agent-card"
)

# Invocation
response = await a2a_client.invoke_skill(
    agent_card,
    skill_id="get_logs",
    params={
        "stream_id": "12345",
        "start_time": 1630000000,
        "end_time": 1630003600
    },
    payment=eip712_signature
)
```

**Integración con nuestro sistema**:
- Cada seller publica AgentCard en `/.well-known/agent-card`
- Buyers usan A2A discovery para encontrar sellers
- Skills declaran precios y schemas
- Payment method es `x402-eip3009`

---

### x402 Protocol: HTTP Micropayments

**Spec**: https://www.x402.org

**Flow**:

1. **402 Payment Required**
```http
HTTP/1.1 402 Payment Required
Content-Type: application/json

{
  "error": "Payment required",
  "accepts": [
    {
      "kind": "evm-eip3009-USDC",
      "asset": {
        "address": "0x...",
        "network": "avalanche-fuji"
      },
      "amount": "10000",
      "recipient": "0x...",
      "facilitator": "https://facilitator.ultravioletadao.xyz"
    }
  ]
}
```

2. **Payment Submission**
```http
POST /api/resource
X-Payment: {"kind": "evm-eip3009-USDC", "payload": {...}}

Body: {...}
```

3. **Facilitator Verification**
```
Client → Facilitator /verify → Verifica firma
Facilitator /settle → Ejecuta transferWithAuthorization
Server recibe confirmación → Retorna recurso
```

**Ventajas**:
- ✅ Estándar HTTP (status code 402)
- ✅ Stateless (facilitator no guarda estado)
- ✅ Gasless (EIP-3009 meta-transactions)
- ✅ Atómico (pago + recurso en una request)

---

### EIP-3009: Transfer With Authorization

**Spec**: https://eips.ethereum.org/EIPS/eip-3009

**Función principal**:
```solidity
function transferWithAuthorization(
    address from,
    address to,
    uint256 value,
    uint256 validAfter,
    uint256 validBefore,
    bytes32 nonce,
    uint8 v,
    bytes32 r,
    bytes32 s
) external;
```

**Cómo funciona**:
1. Usuario firma EIP-712 message off-chain
2. Cualquiera puede enviar la firma on-chain (relayer/facilitator)
3. Contrato verifica firma y ejecuta transfer
4. Usuario no paga gas, el relayer sí

**Ventajas para agentes AI**:
- ✅ No necesitan ETH/AVAX para gas
- ✅ Pueden operar sin wallets custodiales
- ✅ Facilitator paga gas, recupera en fees (opcional)

**Implementación en UVD V2** (erc-20/src/UVD_V2.sol):
```solidity
contract UVD_V2 is ERC20, ERC20Permit, Ownable {
    // EIP-3009 typehash
    bytes32 public constant TRANSFER_WITH_AUTHORIZATION_TYPEHASH = keccak256(
        "TransferWithAuthorization(address from,address to,uint256 value,uint256 validAfter,uint256 validBefore,bytes32 nonce)"
    );

    // Nonces usados (replay protection)
    mapping(address => mapping(bytes32 => bool)) public authorizationState;

    function transferWithAuthorization(
        address from,
        address to,
        uint256 value,
        uint256 validAfter,
        uint256 validBefore,
        bytes32 nonce,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external {
        // 1. Validar time window
        require(block.timestamp > validAfter, "Authorization not yet valid");
        require(block.timestamp < validBefore, "Authorization expired");

        // 2. Validar nonce (replay protection)
        require(!authorizationState[from][nonce], "Authorization already used");

        // 3. Build EIP-712 digest
        bytes32 structHash = keccak256(
            abi.encode(
                TRANSFER_WITH_AUTHORIZATION_TYPEHASH,
                from, to, value, validAfter, validBefore, nonce
            )
        );
        bytes32 digest = _hashTypedDataV4(structHash);

        // 4. Recover signer from signature
        address signer = ecrecover(digest, v, r, s);
        require(signer == from, "Invalid signature");
        require(signer != address(0), "Invalid signer");

        // 5. Marcar nonce como usado
        authorizationState[from][nonce] = true;

        // 6. Ejecutar transfer
        _transfer(from, to, value);

        emit AuthorizationUsed(from, nonce);
    }

    // Cancel authorization to prevent replay
    function cancelAuthorization(
        address authorizer,
        bytes32 nonce,
        uint8 v, bytes32 r, bytes32 s
    ) external {
        require(!authorizationState[authorizer][nonce], "Authorization already used");

        // Verify signature & mark as used (canceled)
        // ... (verification logic)

        authorizationState[authorizer][nonce] = true;
        emit AuthorizationCanceled(authorizer, nonce);
    }
}
```

---

### CrewAI: Multi-Agent Orchestration

**Uso en el sistema**:

#### 1. Validator Crew
```python
validator_crew = Crew(
    agents=[
        Agent(
            role="Data Quality Analyst",
            goal="Verify data completeness and format",
            tools=[check_schema, verify_timestamps]
        ),
        Agent(
            role="Fraud Detector",
            goal="Detect fake or duplicate data",
            tools=[similarity_check, blockchain_verify]
        ),
        Agent(
            role="Price Reviewer",
            goal="Ensure fair pricing",
            tools=[market_check, historical_prices]
        )
    ],
    tasks=[
        Task(description="Analyze data quality", agent=quality_analyst),
        Task(description="Check for fraud", agent=fraud_detector),
        Task(description="Review price fairness", agent=price_reviewer)
    ]
)
```

#### 2. Seller Crew (Data Formatting)
```python
seller_crew = Crew(
    agents=[
        Agent(
            role="Data Formatter",
            goal="Format logs for consumption",
            tools=[json_formatter, timestamp_converter]
        ),
        Agent(
            role="Quality Assurance",
            goal="Ensure data meets standards",
            tools=[schema_validator, completeness_check]
        )
    ]
)
```

---

## 📚 Guías de Desarrollo

### Configuración del Entorno

#### Requisitos Previos

- **Python 3.11+**
- **Rust 1.75+** (para x402-rs)
- **Foundry** (forge, cast, anvil)
- **Node.js 18+** (opcional, para herramientas)
- **Git**

#### Instalación

```bash
# 1. Clonar repositorio
git clone https://github.com/ultravioletdao/karmacadabra.git
cd karmacadabra

# 2. Instalar Foundry
curl -L https://foundry.paradigm.xyz | bash
foundryup

# 3. Instalar Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 4. Setup Python virtual environments
cd karma-hello-agent
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cd ../abracadabra-agent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd ../validator
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Build x402-rs facilitator
cd ../x402-rs
cargo build --release
```

---

### Despliegue Paso a Paso

#### Step 1: Deploy UVD V2 Token

```bash
cd erc-20

# 1. Configurar .env
cp .env.example .env
# Editar .env con tu PRIVATE_KEY

# 2. Compilar
forge build

# 3. Deploy a Fuji
./deploy-fuji.sh

# Output esperado:
# ✅ UVD V2 Token deployed: 0x1234...5678
# Save this address in deployment.json
```

#### Step 2: Deploy ERC-8004 Registries

```bash
cd ../erc-8004

# 1. Configurar .env
cp .env.fuji.example .env.fuji
source .env.fuji

# 2. Compilar
cd contracts
forge build

# 3. Deploy
cd ..
./deploy-fuji.sh

# Output esperado:
# ✅ IdentityRegistry: 0xaaaa...bbbb
# ✅ ReputationRegistry: 0xcccc...dddd
# ✅ ValidationRegistry: 0xeeee...ffff
```

#### Step 3: Setup x402 Facilitator

```bash
cd ../x402-rs

# 1. Configurar .env
cat > .env << EOF
SIGNER_TYPE=private-key
EVM_PRIVATE_KEY=0x...
RPC_URL_FUJI=https://avalanche-fuji-c-chain-rpc.publicnode.com
HOST=0.0.0.0
PORT=8080
RUST_LOG=info
EOF

# 2. Agregar UVD token a src/network.rs
# (Ver guía en x402-rs/README.md)

# 3. Build
cargo build --release

# 4. Run locally para testing
cargo run

# 5. Deploy a servidor (ejemplo con Docker)
docker build -t x402-facilitator .
docker run -d \
  --name facilitator \
  --env-file .env \
  -p 8080:8080 \
  x402-facilitator

# 6. Setup HTTPS con Caddy/nginx
# facilitator.ultravioletadao.xyz → localhost:8080
```

#### Step 4: Deploy Validator Agent

```bash
cd ../validator

# 1. Configurar
cp .env.example .env
# Editar con:
# - RPC_URL=https://avalanche-fuji-c-chain-rpc.publicnode.com
# - PRIVATE_KEY=...
# - IDENTITY_REGISTRY=0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618  # ✅ DEPLOYED
# - REPUTATION_REGISTRY=0x932d32194C7A47c0fe246C1d61caF244A4804C6a  # ✅ DEPLOYED
# - VALIDATION_REGISTRY=0x9aF4590035C109859B4163fd8f2224b820d11bc2  # ✅ DEPLOYED
# - OPENAI_API_KEY=... (para CrewAI)

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Registrar agente
python -c "
from agents.validator_agent import ValidatorAgent
agent = ValidatorAgent(
    agent_domain='validator.ultravioletadao.xyz',
    private_key=os.getenv('PRIVATE_KEY')
)
agent_id = agent.register_agent()
print(f'Validator registered with ID: {agent_id}')
"

# 4. Run
python main.py
```

#### Step 5: Deploy Karma-Hello Agents

```bash
cd ../karma-hello-agent

# 1. Configurar
cp .env.example .env
# Agregar:
# - MONGO_URI (conexión a karma-hello DB)
# - UVD_TOKEN_ADDRESS
# - FACILITATOR_URL=https://facilitator.ultravioletadao.xyz
# - VALIDATOR_AGENT_ID=3

# 2. Registrar seller
python -c "
from agents.karma_hello_seller import KarmaHelloSeller
seller = KarmaHelloSeller()
seller_id = seller.register_agent()
print(f'KarmaHello Seller ID: {seller_id}')
"

# 3. Run seller API
python main.py --mode seller --port 8081

# 4. Run buyer (en otra terminal)
python main.py --mode buyer
```

#### Step 6: Deploy Abracadabra Agents

```bash
cd ../abracadabra-agent

# 1. Configurar
cp .env.example .env
# Agregar:
# - SQLITE_DB_PATH=path/to/analytics.db
# - COGNEE_CONFIG...

# 2. Registrar seller
python -c "
from agents.abracadabra_seller import AbracadabraSeller
seller = AbracadabraSeller()
seller_id = seller.register_agent()
print(f'Abracadabra Seller ID: {seller_id}')
"

# 3. Run seller API
python main.py --mode seller --port 8082

# 4. Run buyer
python main.py --mode buyer
```

#### Step 7: Testing End-to-End

```bash
# Demo script
python demo.py

# Output esperado:
# ✅ All contracts deployed
# ✅ All agents registered
# ✅ KarmaHello bought transcript from Abracadabra
#    - Payment: 0.02 UVD
#    - Validation score: 95/100
#    - Data received: 1.2 MB
# ✅ Abracadabra bought logs from KarmaHello
#    - Payment: 0.01 UVD
#    - Validation score: 98/100
#    - Data received: 450 KB
# ✅ All transactions verified on-chain
# 🎉 Demo completed successfully!
```

---

### Testing Local

#### Setup Anvil (Local Testnet)

```bash
# Terminal 1: Run Anvil
anvil --chain-id 43113 --port 8545

# Terminal 2: Deploy contracts
cd erc-20
forge script script/Deploy.s.sol \
  --rpc-url http://localhost:8545 \
  --broadcast

cd ../erc-8004
forge script script/Deploy.s.sol \
  --rpc-url http://localhost:8545 \
  --broadcast

# Terminal 3: Run facilitator
cd ../x402-rs
RPC_URL_FUJI=http://localhost:8545 cargo run

# Terminales 4-6: Run agents
cd ../validator && python main.py
cd ../karma-hello-agent && python main.py --mode seller
cd ../abracadabra-agent && python main.py --mode seller

# Terminal 7: Run demo
python demo.py --network local
```

---

## 📖 Referencias

### Documentación Oficial

- **ERC-8004 Spec**: https://eips.ethereum.org/EIPS/eip-8004
- **A2A Protocol**: https://ai.pydantic.dev/a2a/
- **x402 Protocol**: https://www.x402.org
- **EIP-3009**: https://eips.ethereum.org/EIPS/eip-3009
- **EIP-712**: https://eips.ethereum.org/EIPS/eip-712
- **CrewAI Docs**: https://docs.crewai.com

### Trustless Agents Course

- **URL**: https://intensivecolearn.ing/en/programs/trustless-agents
- **Contenido**:
  - Week 1: Agent identity and registration
  - Week 2: Trust models (feedback, validation)
  - Week 3: Payment integration (x402)
  - Week 4: Multi-agent orchestration
  - Week 5: Building a trustless marketplace

### Repositorios de Referencia

- **ERC-8004 Example**: `z:\erc8004\erc-8004-example`
- **A2A Samples**: https://github.com/a2aproject/a2a-samples
- **x402-rs**: https://github.com/polyphene/x402-rs

### Herramientas

- **Foundry**: https://book.getfoundry.sh
- **Snowtrace (Fuji)**: https://testnet.snowtrace.io
- **Avalanche Faucet**: https://faucet.avax.network
- **Pydantic AI**: https://ai.pydantic.dev

---

## 💰 Monetización y Productos

**Documento completo**: Ver `MONETIZATION_OPPORTUNITIES.md` para análisis detallado de 50+ servicios comercializables.

### Resumen de Servicios por Agente

**Karma-Hello Agent** (6 Tiers de servicios):
- **Tier 1** (0.01-0.05 UVD): Chat logs, User activity, Token economics
- **Tier 2** (0.05-0.15 UVD): ML predictions, User segmentation, Sentiment analysis
- **Tier 3** (0.15-0.30 UVD): Fraud detection, Economic health, Gamification insights
- **Tier 4** (0.30-1.00 UVD): A/B testing, Custom ML models, Real-time intelligence
- **Tier 5** (Custom): White-label gamification, Token economy design
- **Fuente de datos**: MongoDB en `z:\ultravioleta\ai\cursor\karma-hello`

**Abracadabra Agent** (6 Tiers de servicios):
- **Tier 1** (0.02-0.08 UVD): Raw transcripts, Enhanced transcripts, Multi-language
- **Tier 2** (0.10-0.25 UVD): Clip generation, Blog posts, Social media packs
- **Tier 3** (0.25-0.50 UVD): Predictive engine, Recommendations, Knowledge graph search
- **Tier 4** (0.50-2.00 UVD): Auto video editing, Image generation, Auto publishing
- **Tier 5** (0.80-3.00 UVD): Deep idea extraction, Audio analysis, Advanced A/B testing
- **Tier 6** (Custom): Multi-stream aggregation, Team management, Custom AI models
- **Fuente de datos**: SQLite analytics.db + Cognee en `z:\ultravioleta\ai\cursor\abracadabra`

**Validator Agent**:
- **Fee básico**: 0.001 UVD por validación
- **Servicios**: Validación de calidad de datos, fraud detection, compliance

**Bundles Cross-Platform** (20-30% descuento):
- Complete Stream Context (0.25 UVD)
- Auto Content Generator (1.80 UVD)
- Predictive Intelligence Package (0.90 UVD)

### Implementación por Fase

**Phase 3-4** (Semanas 4-5): Servicios Tier 1-2
- Karma-Hello: Chat logs, ML predictions, sentiment
- Abracadabra: Transcripts, clips, blog generation
- **Revenue esperado**: 0.01-0.25 UVD por request

**Phase 5** (Semana 6): Servicios Tier 3-4
- Fraud detection, video editing, real-time intelligence
- **Revenue esperado**: 0.15-2.00 UVD por request

**Phase 6+** (Mes 2+): Servicios Tier 5-6 Enterprise
- Custom models, white-label, consulting
- **Revenue esperado**: 10-200 UVD por proyecto

---

## 🎯 Próximos Pasos

### Inmediatos (Hoy)

1. [ ] Crear estructura de directorios completa
2. [ ] Escribir todos los READMEs base
3. [ ] Setup repositorio Git
4. [ ] Crear branch `feature/phase-1-blockchain`

### Esta Semana

1. [ ] Implementar UVD V2 Token
2. [ ] Deploy ERC-8004 a Fuji
3. [ ] Configurar x402 facilitator
4. [ ] Testing de infraestructura

### Próximas 2 Semanas

1. [ ] Base agent architecture
2. [ ] Validator agent
3. [ ] Karma-Hello agents (con servicios Tier 1-2)
4. [ ] Testing integración

---

## 📝 Notas de Implementación

### Consideraciones de Seguridad

1. **Private Keys**:
   - NUNCA commitear `.env` files
   - Usar wallets de testing para Fuji
   - Rotar keys antes de mainnet

2. **Smart Contracts**:
   - Auditar antes de mainnet
   - Testing exhaustivo en Fuji
   - Rate limiting en facilitator

3. **Agentes**:
   - Validar todos los inputs
   - Rate limiting por IP
   - Monitoring de transacciones anómalas

### Performance

- **Latency objetivo**: <3s por transacción
- **Throughput**: 100 tx/min (Fuji limit)
- **Caching**: Redis para AgentCards
- **Monitoring**: OpenTelemetry + Grafana

### Costos

**Fuji Testnet (gratis)**:
- AVAX testnet: Gratis del faucet
- Transacciones: Gratis (gas pagado con AVAX testnet)

**Mainnet (futuro)**:
- UVD tokens: $0.01 USD cada uno
- Gas per transaction: ~$0.001-0.01 AVAX
- Facilitator: $50/mes servidor

---

## ✅ Checklist de Finalización

### Phase 1: Blockchain Infrastructure
- [ ] UVD V2 deployed on Fuji
- [ ] ERC-8004 registries deployed
- [ ] x402 facilitator running
- [ ] All contracts verified on Snowtrace
- [ ] Testing suite passing

### Phase 2: Base Agents
- [ ] base_agent.py implemented
- [ ] Validator agent working
- [ ] ERC-8004 integration complete
- [ ] A2A protocol working
- [ ] CrewAI crews functional

### Phase 3-4: Service Agents
- [ ] Karma-Hello seller/buyer deployed
- [ ] Abracadabra seller/buyer deployed
- [ ] Both APIs with x402 working
- [ ] Data integration complete

### Phase 5: Testing & Demo
- [ ] End-to-end flow working
- [ ] Demo script complete
- [ ] Video tutorial recorded
- [ ] Full documentation written
- [ ] Ready for presentation

---

**🎉 Fin del Master Plan**

Este documento es la guía completa para implementar el ecosistema de trustless agents. Sigue las fases secuencialmente y usa los READMEs de cada componente para detalles específicos.

**Última actualización**: Octubre 2025
**Versión**: 1.0.0
**Autor**: Ultravioleta DAO
**License**: MIT
