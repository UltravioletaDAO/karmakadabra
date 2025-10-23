# 🏗️ Architecture Documentation

> Arquitectura técnica detallada del ecosistema de Trustless Agents

**Última actualización**: Octubre 2025
**Versión**: 1.0.0

---

## 📋 Tabla de Contenidos

1. [Stack Tecnológico](#stack-tecnológico)
2. [Capas del Sistema](#capas-del-sistema)
3. [Flujos de Datos](#flujos-de-datos)
4. [Protocolos](#protocolos)
5. [Decisiones de Diseño](#decisiones-de-diseño)

---

## 🛠️ Stack Tecnológico

### Blockchain Layer

| Componente | Tecnología | Versión | Propósito |
|------------|-----------|---------|-----------|
| **Network** | Avalanche Fuji | Testnet | Red de pruebas EVM-compatible |
| **Smart Contracts** | Solidity | 0.8.20+ | ERC-8004 Registries + UVD Token |
| **Build Tool** | Foundry | Latest | Compilación y deploy |
| **RPC Provider** | PublicNode | - | Conexión a blockchain |

### Agent Layer

| Componente | Tecnología | Versión | Propósito |
|------------|-----------|---------|-----------|
| **Runtime** | Python | 3.11+ | Ejecución de agentes |
| **Web Framework** | FastAPI | 0.109+ | APIs REST |
| **AI Orchestration** | CrewAI | 0.28+ | Multi-agent workflows |
| **LLM** | OpenAI GPT-4o | - | Análisis y validación |
| **Web3** | web3.py | 6.15+ | Interacción blockchain |
| **EIP-712 Signing** | eth-account | 0.11+ | Firmas meta-transacciones |

### Protocol Layer

| Componente | Tecnología | Versión | Propósito |
|------------|-----------|---------|-----------|
| **Payment Protocol** | x402 (Rust) | 0.3+ | HTTP micropagos |
| **Agent Protocol** | A2A (Pydantic AI) | 0.0.7+ | Comunicación agente-a-agente |
| **Server Middleware** | x402-axum | 0.3+ | Payment gating (Rust) |
| **Client Middleware** | x402-reqwest | 0.3+ | Payment client (Rust) |

### Data Layer

| Componente | Tecnología | Versión | Propósito |
|------------|-----------|---------|-----------|
| **Karma-Hello DB** | MongoDB | 6.0+ | Logs de streams |
| **Abracadabra DB** | SQLite | 3.40+ | Transcripciones |
| **Knowledge Graph** | Cognee | Latest | Búsqueda semántica |

---

## 🏛️ Capas del Sistema

### Capa 1: Blockchain (Fuji Testnet)

```
┌─────────────────────────────────────────────────────────────┐
│                    AVALANCHE FUJI TESTNET                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────┐  ┌──────────────────────────┐   │
│  │   GLUE Token         │  │   ERC-8004 Registries    │   │
│  │   (ERC-20 + EIP-3009│  │                          │   │
│  ├──────────────────────┤  ├──────────────────────────┤   │
│  │                      │  │ • IdentityRegistry       │   │
│  │ transferWithAuth()   │  │   - newAgent()           │   │
│  │ permit()             │  │   - resolveByAddress()   │   │
│  │ transfer()           │  │                          │   │
│  │ balanceOf()          │  │ • ReputationRegistry     │   │
│  │                      │  │   - acceptFeedback()     │   │
│  │ EIP-712 Domain:      │  │   - rateClient()         │   │
│  │ - name: "Ultravioleta│  │                          │   │
│  │          DAO"        │  │ • ValidationRegistry     │   │
│  │ - version: "2"       │  │   - validationRequest()  │   │
│  │ - chainId: 43113     │  │   - validationResponse() │   │
│  │                      │  │   - rateValidator()      │   │
│  └──────────────────────┘  └──────────────────────────┘   │
│                                                             │
│  Gas Model: EIP-1559                                        │
│  Block Time: ~2 seconds                                     │
│  Finality: ~1 second                                        │
└─────────────────────────────────────────────────────────────┘
```

**Decisiones**:
- ✅ Fuji testnet → gratis, rápido, compatible con EVM
- ✅ EIP-3009 → gasless transfers esenciales para agentes
- ✅ ERC-8004 → estándar para agent identity y reputation

---

### Capa 2: Payment Facilitator (x402-rs)

```
┌─────────────────────────────────────────────────────────────┐
│         facilitator.ultravioletadao.xyz (x402-rs)           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  HTTP Server (Axum)                                          │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                                                       │ │
│  │  POST /verify                                         │ │
│  │  ├─ Parse PaymentPayload                             │ │
│  │  ├─ Verify EIP-712 signature                         │ │
│  │  ├─ Check balance of payer                           │ │
│  │  └─ Return VerifyResponse {valid: true}              │ │
│  │                                                       │ │
│  │  POST /settle                                         │ │
│  │  ├─ Call UVD.transferWithAuthorization()             │ │
│  │  ├─ Wait for transaction receipt                     │ │
│  │  └─ Return SettleResponse {txHash: "0x..."}          │ │
│  │                                                       │ │
│  │  GET /supported                                       │ │
│  │  └─ Return list of supported payment methods         │ │
│  │                                                       │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  Features:                                                   │
│  • Stateless (no database)                                  │
│  • Multi-network support                                    │
│  • OpenTelemetry tracing                                    │
│  • Concurrent request handling                              │
│                                                             │
│  Performance:                                                │
│  • Latency: <500ms (verify + settle)                       │
│  • Throughput: 100 req/min (Fuji limit)                    │
└─────────────────────────────────────────────────────────────┘
```

**Decisiones**:
- ✅ Rust → performance crítico para micropagos
- ✅ Axum → async HTTP framework moderno
- ✅ Stateless → fácil de escalar horizontalmente

---

### Capa 3: Agent Layer (Python)

```
┌──────────────────────────────────────────────────────────────┐
│                        AGENT LAYER                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Base Agent Architecture                                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  ERC8004BaseAgent                                      │ │
│  │  ├─ Web3 connection                                    │ │
│  │  ├─ Account from private key                           │ │
│  │  ├─ Contract instances (Identity, Reputation, Valid)   │ │
│  │  └─ Methods:                                           │ │
│  │     • register_agent() → agentId                       │ │
│  │     • request_validation(validator_id, data_hash)      │ │
│  │     • submit_validation_response(data_hash, score)     │ │
│  │     • rate_validator(validator_id, rating)             │ │
│  │     • rate_client(client_id, rating)                   │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Seller Agents (Server)                                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  FastAPI + x402-axum                                   │ │
│  │                                                        │ │
│  │  @app.post("/api/resource")                            │ │
│  │  @x402_required(price=UVD.amount("0.01"))              │ │
│  │  async def handle_request(req):                        │ │
│  │      # 1. x402 middleware verifica pago                │ │
│  │      # 2. Si válido, ejecuta handler                   │ │
│  │      # 3. Request validación (opcional)                │ │
│  │      # 4. CrewAI procesa datos                         │ │
│  │      # 5. Retorna respuesta                            │ │
│  │      return {"data": result}                           │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Buyer Agents (Client)                                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  A2A Client + EIP-712 Signer                           │ │
│  │                                                        │ │
│  │  async def purchase():                                 │ │
│  │      # 1. Discovery via A2A                            │ │
│  │      agent_card = await discover(domain)               │ │
│  │                                                        │ │
│  │      # 2. Sign EIP-712 payment                         │ │
│  │      auth = sign_transfer_authorization(...)           │ │
│  │                                                        │ │
│  │      # 3. HTTP request con X-Payment                   │ │
│  │      response = await http.post(                       │ │
│  │          url,                                          │ │
│  │          headers={"X-Payment": json(auth)},            │ │
│  │          json=params                                   │ │
│  │      )                                                 │ │
│  │                                                        │ │
│  │      # 4. Integrar datos recibidos                     │ │
│  │      store_in_db(response.json())                      │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Validator Agent                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  CrewAI Multi-Agent Validation                         │ │
│  │                                                        │ │
│  │  async def validate(data_hash):                        │ │
│  │      # 1. Load data                                    │ │
│  │      data = load_data(data_hash)                       │ │
│  │                                                        │ │
│  │      # 2. CrewAI crew valida                           │ │
│  │      crew = Crew([                                     │ │
│  │          quality_analyst,                              │ │
│  │          fraud_detector,                               │ │
│  │          price_reviewer                                │ │
│  │      ])                                                │ │
│  │      report = crew.kickoff()                           │ │
│  │                                                        │ │
│  │      # 3. Extract score                                │ │
│  │      score = extract_score(report)                     │ │
│  │                                                        │ │
│  │      # 4. Submit on-chain                              │ │
│  │      tx = submit_validation_response(data_hash, score) │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔄 Flujos de Datos

### Flujo Completo: Karma-Hello compra Transcript de Abracadabra

```
FASE 1: DISCOVERY
─────────────────
KarmaHelloBuyer                           AbracadabraSeller
      │                                          │
      │  GET /.well-known/agent-card            │
      │─────────────────────────────────────────>│
      │                                          │
      │  AgentCard {                             │
      │    skills: ["get_transcript"],           │
      │    price: "0.02 UVD",                    │
      │    paymentMethods: ["x402-eip3009"]      │
      │  }                                       │
      │<─────────────────────────────────────────│


FASE 2: PAYMENT SIGNING
────────────────────────
KarmaHelloBuyer
      │
      │  [Off-chain] Sign EIP-712 message
      │  ├─ from: KarmaHello wallet
      │  ├─ to: Abracadabra wallet
      │  ├─ value: 20000 (0.02 UVD)
      │  ├─ validBefore: now + 1h
      │  └─ nonce: random
      │
      │  signature = {v, r, s}
      ▼


FASE 3: PURCHASE REQUEST
─────────────────────────
KarmaHelloBuyer                           AbracadabraSeller
      │                                          │
      │  POST /api/transcripts                   │
      │  X-Payment: {                            │
      │    "kind": "evm-eip3009-UVD",            │
      │    "payload": {v, r, s, from, to, ...}   │
      │  }                                       │
      │  Body: {"stream_id": "12345"}            │
      │─────────────────────────────────────────>│
      │                                          │
      │                                [x402 middleware]
      │                                          │
      │                                Parse X-Payment
      │                                          │
      │                                          ▼
                                          Facilitator
                                               │
                                    POST /verify
                                               │
                                    Verify signature
                                    Check balance
                                               │
                                    200 OK {valid: true}
                                               │
      │                                          │
      │                                [Validation Optional]
      │                                          │
      │                                POST to ValidatorAgent
      │                                          │
      │                                Validator validates
      │                                          │
      │                                Returns score: 95/100
      │                                          │
      │                                          ▼
                                          Facilitator
                                               │
                                    POST /settle
                                               │
                                    Call UVD.transferWithAuth()
                                               │
                                    Wait for tx receipt
                                               │
                                    200 OK {txHash: "0x..."}
                                               │
      │                                          │
      │                                [Execute Handler]
      │                                          │
      │                                Query SQLite DB
      │                                          │
      │                                CrewAI enrichment
      │                                          │
      │                                          │
      │  200 OK                                  │
      │  {                                       │
      │    "transcript": {...},                  │
      │    "topics": [...],                      │
      │    "seller_agent_id": 2                  │
      │  }                                       │
      │<─────────────────────────────────────────│


FASE 4: DATA INTEGRATION
─────────────────────────
KarmaHelloBuyer
      │
      │  Store in MongoDB
      │  ├─ transcripts collection
      │  └─ Link to stream logs
      │
      │  Update knowledge base
      ▼
```

**Timing**:
- Discovery: <100ms (HTTP GET)
- Signing: <10ms (off-chain)
- Verification: <200ms (RPC call para balance check)
- Settlement: <2s (blockchain tx)
- Handler execution: <1s (DB query + CrewAI)

**Total: ~3-4 segundos**

---

## 🔐 Protocolos

### EIP-712: Typed Structured Data Hashing

**Purpose**: Firmas seguras y legibles para meta-transacciones.

**Domain**:
```json
{
  "name": "Ultravioleta DAO",
  "version": "2",
  "chainId": 43113,
  "verifyingContract": "0xUVD_TOKEN_ADDRESS"
}
```

**Types**:
```json
{
  "TransferWithAuthorization": [
    {"name": "from", "type": "address"},
    {"name": "to", "type": "address"},
    {"name": "value", "type": "uint256"},
    {"name": "validAfter", "type": "uint256"},
    {"name": "validBefore", "type": "uint256"},
    {"name": "nonce", "type": "bytes32"}
  ]
}
```

**Message**:
```json
{
  "from": "0xBUYER",
  "to": "0xSELLER",
  "value": "20000",
  "validAfter": "0",
  "validBefore": "1730123456",
  "nonce": "0xabc123..."
}
```

**Hash Calculation**:
```
structHash = keccak256(encodeType(message))
domainSeparator = keccak256(encodeDomain(domain))
digest = keccak256("\x19\x01" + domainSeparator + structHash)
```

**Signature**:
```
{v, r, s} = sign(digest, privateKey)
```

---

### A2A Protocol: Agent-to-Agent Communication

**Discovery Endpoint**: `GET /.well-known/agent-card`

**AgentCard Schema**:
```typescript
interface AgentCard {
  agentId: number;
  name: string;
  description: string;
  version: string;
  skills: Skill[];
  trustModels: string[];  // ["erc-8004"]
  paymentMethods: string[];  // ["x402-eip3009-UVD"]
  registrations: Registration[];
}

interface Skill {
  skillId: string;
  name: string;
  description: string;
  price: {
    amount: string;  // "0.01"
    currency: string;  // "UVD"
  };
  inputSchema: JSONSchema;
  outputSchema: JSONSchema;
}
```

**Invocation**:
```python
response = await a2a_client.invoke_skill(
    agent_card,
    skill_id="get_logs",
    params={"stream_id": "12345"},
    payment=eip712_signature
)
```

---

### x402 Protocol: HTTP Payment Required

**402 Response**:
```http
HTTP/1.1 402 Payment Required
Content-Type: application/json

{
  "error": "Payment required",
  "accepts": [
    {
      "kind": "evm-eip3009-UVD",
      "asset": {
        "address": "0xUVD_TOKEN",
        "network": "avalanche-fuji",
        "decimals": 6
      },
      "amount": "10000",
      "recipient": "0xSELLER",
      "facilitator": "https://facilitator.ultravioletadao.xyz"
    }
  ],
  "x402Version": 1
}
```

**Payment Header**:
```http
X-Payment: {
  "kind": "evm-eip3009-UVD",
  "payload": {
    "from": "0xBUYER",
    "to": "0xSELLER",
    "value": "10000",
    "validAfter": "0",
    "validBefore": "1730123456",
    "nonce": "0xabc...",
    "v": 27,
    "r": "0x...",
    "s": "0x..."
  }
}
```

---

## 💡 Decisiones de Diseño

### ¿Por qué Fuji en lugar de Mainnet?

✅ **Testing sin costo**: AVAX gratis del faucet
✅ **Iteración rápida**: Deploy instantáneo sin preocuparse por gas
✅ **Same execution environment**: EVM idéntico a Mainnet
✅ **Fácil migración**: Mismo código funciona en Mainnet

**Cuando migrar a Mainnet**:
- ✅ Sistema testeado exhaustivamente
- ✅ Auditoría de contratos completa
- ✅ Suficientes usuarios reales
- ✅ Modelo económico viable

---

### ¿Por qué x402 en lugar de Web3Modal + MetaMask?

✅ **UX superior**: No pop-ups de confirmación
✅ **Gasless**: Usuarios no necesitan AVAX
✅ **HTTP nativo**: Standard 402 status code
✅ **Micropagos**: Optimizado para <$0.01 USD

**vs. Web3Modal**:
- ❌ Requiere MetaMask instalado
- ❌ Pop-up por cada pago
- ❌ Usuario paga gas
- ❌ No es HTTP-native

---

### ¿Por qué CrewAI en lugar de LangChain/AutoGPT?

✅ **Multi-agent nativo**: Diseñado para crews
✅ **Task delegation**: Agentes pueden delegar
✅ **Simple API**: Menos boilerplate
✅ **Good defaults**: Funciona out-of-the-box

**vs. LangChain**:
- ✅ Más enfocado en multi-agent
- ✅ Menos configuración necesaria
- ✅ Mejor para validation workflows

---

### ¿Por qué MongoDB + SQLite en lugar de PostgreSQL?

**MongoDB (Karma-Hello)**:
- ✅ JSON-native: Logs son objetos JSON
- ✅ Flexible schema: Datos de Twitch cambian
- ✅ Already in use: Sistema existente

**SQLite (Abracadabra)**:
- ✅ Embedded: No servidor separado
- ✅ Fast queries: Analytics DB optimizada
- ✅ Simple backup: Single file
- ✅ Already in use: Sistema existente

**Migration path**: Si crece, migrar a Postgres con Timescale

---

## 📊 Performance & Scalability

### Current Limits (Fuji Testnet)

| Metric | Value | Bottleneck |
|--------|-------|------------|
| Max tx/block | ~50 | Fuji capacity |
| Block time | 2s | Chain consensus |
| Finality | 1s | C-Chain finality |
| API latency | <3s | Network + settlement |
| Throughput | ~100 tx/min | RPC rate limits |

### Scaling Strategy

**Phase 1: Vertical (Single Server)**
- ✅ Async Python (FastAPI)
- ✅ Connection pooling (MongoDB/SQLite)
- ✅ Caching (Redis for AgentCards)
- ✅ Capacity: ~1000 users

**Phase 2: Horizontal (Multiple Servers)**
- Load balancer
- Multiple FastAPI instances
- Shared Redis cache
- Capacity: ~10k users

**Phase 3: Distributed**
- Separate seller/buyer/validator services
- Message queue (RabbitMQ/Kafka)
- Microservices architecture
- Capacity: ~100k+ users

---

**Ver [MASTER_PLAN.md](./MASTER_PLAN.md) para roadmap de implementación.**
