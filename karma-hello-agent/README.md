# 🎮 Karma-Hello Agent System

> Agentes AI autónomos que comercializan logs de streams de Twitch usando ERC-8004 + A2A + x402

**Versión**: 1.0.0
**Network**: Avalanche Fuji Testnet
**Estado**: 🔴 Por implementar
**Última actualización**: Octubre 21, 2025

---

## 🗂️ Ubicación en el Proyecto

```
z:\ultravioleta\dao\karmacadabra\
├── erc-20/                    (GLUE Token - RECIBE pagos aquí)
├── erc-8004/                  (SE REGISTRA como Agent ID 1 y 4)
├── x402-rs/                   (USA facilitator para pagos)
├── validator/                 (SOLICITA validaciones antes de venta)
├── karma-hello-agent/         ← ESTÁS AQUÍ
├── abracadabra-agent/         (COMPRA transcripts / VENDE logs)
├── MASTER_PLAN.md
└── MONETIZATION_OPPORTUNITIES.md (VER productos completos aquí)
```

**Parte del Master Plan**: Phase 3 - Karma-Hello Agents (Semana 4)

**Fuente de datos**: `z:\ultravioleta\ai\cursor\karma-hello` (MongoDB)

---

## 📋 Tabla de Contenidos

1. [Descripción](#-descripción)
2. [Arquitectura](#-arquitectura)
3. [Agentes](#-agentes)
4. [Instalación](#-instalación)
5. [Configuración](#-configuración)
6. [Uso](#-uso)
7. [API](#-api)
8. [Integración](#-integración)

---

## 🎯 Descripción

El **Karma-Hello Agent System** son agentes AI que comercializan datos de streams de Twitch del sistema [karma-hello](z:\ultravioleta\ai\cursor\karma-hello).

### 💰 Productos que Vende (50+ servicios)

**Ver catálogo completo en**: `MONETIZATION_OPPORTUNITIES.md` § Karma-Hello Servicios

**Tier 1** (0.01-0.05 UVD) - Datos Básicos:
- ✅ Chat Logs & Messages (0.01 UVD)
- ✅ User Activity Stream (0.02 UVD)
- ✅ Token Economics Data (0.03 UVD)

**Tier 2** (0.05-0.15 UVD) - Analytics:
- ✅ ML Predictions (burns, churn, anomalies) - 0.10 UVD
- ✅ User Segmentation (Whales, Burners, etc.) - 0.08 UVD
- ✅ Sentiment & NLP Analysis - 0.06 UVD

**Tier 3** (0.15-0.30 UVD) - Advanced Intelligence:
- ✅ Fraud Detection Service - 0.20 UVD
- ✅ Economic Health Dashboard - 0.25 UVD
- ✅ Gamification Intelligence - 0.15 UVD

**Tier 4** (0.30-1.00 UVD) - Premium:
- ✅ A/B Testing as a Service - 0.50 UVD/test
- ✅ Custom ML Model Training - 1.00 UVD
- ✅ Real-Time Stream Intelligence - 0.40 UVD/hora

**Tier 5-6** (Custom Pricing) - Enterprise:
- White-Label Gamification (50-200 UVD)
- Token Economy Design (100 UVD)
- Compliance & Auditing (20 UVD/mes)

**Total**: 20+ servicios comercializables

### Datos Disponibles en MongoDB

Karma-Hello registra en MongoDB (`z:\ultravioleta\ai\cursor\karma-hello`):
- **Chat messages** con timestamps precisos
- **User activity** (joins, parts, subs, raids)
- **Token rewards** distribuidos (Chat-to-Earn)
- **Stream events** (host, raid, bits, etc.)
- **User metadata** (badges, colors, roles)
- **Analytics** (engagement, sentiment, top chatters)
- **ML models** (predictions, anomaly detection)
- **A/B tests** resultados históricos

### Problema que Resuelve

Abracadabra tiene **transcripciones de audio**, pero NO sabe:
- ¿Qué decía el chat durante ese momento?
- ¿Hubo eventos importantes (raid, host)?
- ¿Qué usuarios estaban activos?
- ¿Cómo reaccionó la comunidad?

**Solución**: Comprar logs de Karma-Hello para enriquecer las transcripciones con contexto completo del stream.

### 🛒 Productos que Compra

**Karma-Hello Buyer** compra de Abracadabra:
- ✅ Raw Transcripts (0.02 UVD)
- ✅ Enhanced Transcripts con topics (0.05 UVD)
- ✅ Clip suggestions (0.15 UVD)

**Caso de uso**: Correlacionar logs del chat con lo que decía el streamer en audio.

---

## 📂 Estructura de Datos - PRODUCTOS A VENDER

### Ubicación Local de Productos

```
z:\ultravioleta\dao\karmacadabra\karma-hello-agent\
├── logs/                              ← PRODUCTOS AQUÍ
│   ├── 20251014/                     # Logs por fecha
│   │   ├── full.txt                  # ✅ Chat completo del día
│   │   ├── 0xultravioleta.txt        # Logs por usuario
│   │   ├── psilocibin3.txt           # Logs por usuario
│   │   └── unknown.txt               # Mensajes sin user ID
│   ├── 20251015/
│   ├── 20251016/
│   ├── 20251017/
│   ├── 20251020/                     # Ejemplo actual
│   │   ├── full.txt                  # 11KB - Chat completo
│   │   ├── elboorja.txt              # 1.5KB - Usuario activo
│   │   ├── psilocibin3.txt           # 865B
│   │   ├── sanvalencia2.txt          # 999B
│   │   ├── acpm444.txt               # 370B
│   │   ├── juanjumagalp.txt          # 782B
│   │   └── [30+ usuarios más...]
│   └── 20251021/                     # Último día
└── README.md
```

### Formato de Datos en `logs/YYYYMMDD/`

**`full.txt`** - Chat completo del stream:
```
[10/20/2025 2:45:11 PM] psilocibin3: te han tocado despliegues de sistemas distribuidos con múltiples microservicios con kubernetes y vueltas así?
[10/20/2025 2:52:14 PM] elboorja: Pero es que en eso uno también debe saber hacer bien los prompt...
[10/20/2025 3:04:54 PM] elboorja: Pero la comunicación entre agentes es igual cotidiana?
```

**`{username}.txt`** - Mensajes individuales por usuario:
```
[10/20/2025 2:45:11 PM] psilocibin3: te han tocado despliegues...
[10/20/2025 2:47:32 PM] psilocibin3: Ok stream montando UltravioletaDao Facilitator
```

### Fuente Original (MongoDB)

**Producción**: `z:\ultravioleta\ai\cursor\karma-hello` (MongoDB)

**Colecciones**:
- `messages` - Todos los mensajes del chat
- `user_activity` - Joins, parts, subs, raids
- `stream_sessions` - Metadata de streams
- `token_burns` - Economía de tokens
- `analytics` - Métricas agregadas

**Nota**: Los archivos en `karma-hello-agent/logs/` son **copias exportadas** de MongoDB para testing. El agente en producción consultará directamente MongoDB.

### CrewAI Agent: Dónde Buscar Datos

```python
# En karma_hello_seller.py

class KarmaHelloSeller(ERC8004BaseAgent):
    def __init__(self, config):
        # OPCIÓN 1: Desarrollo/Testing - Leer archivos locales
        self.logs_path = "z:\\ultravioleta\\dao\\karmacadabra\\karma-hello-agent\\logs"

        # OPCIÓN 2: Producción - Conectar a MongoDB real
        self.mongo_uri = config.MONGO_URI  # z:\ultravioleta\ai\cursor\karma-hello
        self.db = MongoClient(self.mongo_uri)["karma_hello"]

    async def get_logs(self, date: str, user: str = None):
        # TESTING: Leer de archivos locales
        if config.USE_LOCAL_FILES:
            log_file = f"{self.logs_path}/{date}/full.txt"
            if user:
                log_file = f"{self.logs_path}/{date}/{user}.txt"
            with open(log_file, 'r') as f:
                return f.read()

        # PRODUCCIÓN: Query MongoDB
        else:
            query = {"date": date}
            if user:
                query["username"] = user
            return self.db.messages.find(query)
```

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                   Karma-Hello Agent System                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────┐      ┌──────────────────────┐   │
│  │  KarmaHelloSeller    │      │  KarmaHelloBuyer     │   │
│  │  (Server Agent)      │      │  (Client Agent)      │   │
│  ├──────────────────────┤      ├──────────────────────┤   │
│  │                      │      │                      │   │
│  │  • ERC-8004 ID: 1    │      │  • ERC-8004 ID: 4    │   │
│  │  • Domain:           │      │  • A2A Client        │   │
│  │    karma-hello-      │      │  • x402 Payment      │   │
│  │    seller.uvdao.xyz  │      │    Signer            │   │
│  │                      │      │  • Auto-buyer        │   │
│  │  • API REST          │      │    Logic             │   │
│  │  • x402 middleware   │      │                      │   │
│  │  • MongoDB query     │      │  Compra:             │   │
│  │  • CrewAI format     │      │  • Transcripts       │   │
│  │                      │      │    from Abracadabra  │   │
│  │  Vende:              │      │                      │   │
│  │  • Stream logs       │      │  Paga:               │   │
│  │  • Chat messages     │      │  • 0.02 UVD          │   │
│  │  • Events            │      │    (gasless)         │   │
│  │                      │      │                      │   │
│  │  Precio:             │      │                      │   │
│  │  • 0.01 UVD/query    │      │                      │   │
│  │                      │      │                      │   │
│  └──────────┬───────────┘      └──────────┬───────────┘   │
│             │                             │               │
│             ▼                             ▼               │
│  ┌─────────────────────────────────────────────────────┐  │
│  │           Base Agent (ERC-8004 + A2A)              │  │
│  ├─────────────────────────────────────────────────────┤  │
│  │  • Web3 connection (Fuji)                          │  │
│  │  • ERC-8004 registry interaction                   │  │
│  │  • A2A protocol client/server                      │  │
│  │  • EIP-712 signing for payments                    │  │
│  │  • CrewAI base setup                               │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
│  Data Source:                                               │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  MongoDB: karma_hello database                      │  │
│  │  • messages collection                              │  │
│  │  • user_activity collection                         │  │
│  │  • stream_sessions collection                       │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🤖 Agentes

### 1. KarmaHelloSeller (Server Agent)

**Rol**: Agente vendedor que expone API para vender logs.

**Features**:
- ✅ API REST con x402 middleware
- ✅ Autenticación via EIP-3009 signatures
- ✅ Queries optimizadas a MongoDB
- ✅ CrewAI para formateo de datos
- ✅ AgentCard publicación (A2A)
- ✅ Registro en ERC-8004 IdentityRegistry

**Endpoints**:

```
GET  /.well-known/agent-card       # A2A discovery
POST /api/logs                      # Vender logs (requiere pago)
POST /api/logs/search               # Búsqueda por keywords
POST /api/logs/users/:user_id       # Logs de un usuario
POST /api/logs/timerange            # Logs en rango de tiempo
GET  /api/price                     # Consultar precios
```

**Precio**:
- 0.01 UVD por query básica
- 0.005 UVD adicional por enrichment con CrewAI
- 0.001 UVD por validación (opcional)

**Implementación**:

```python
from agents.base_agent import ERC8004BaseAgent
from a2a import A2AServer, Skill, AgentCard
from x402 import x402_required
from crewai import Agent, Task, Crew
from pymongo import MongoClient

class KarmaHelloSeller(ERC8004BaseAgent, A2AServer):
    def __init__(self, config):
        super().__init__(
            agent_domain="karma-hello-seller.ultravioletadao.xyz",
            private_key=config.SELLER_PRIVATE_KEY
        )

        # MongoDB connection
        self.mongo = MongoClient(config.MONGO_URI)
        self.db = self.mongo["karma_hello"]

        # CrewAI setup
        self.setup_crew()

        # Register agent on-chain
        self.agent_id = self.register_agent()

        # Publish AgentCard
        self.publish_agent_card()

    def setup_crew(self):
        self.data_formatter = Agent(
            role="Data Formatter",
            goal="Format raw logs into structured, clean data",
            backstory="Expert in data cleaning and formatting",
            tools=[JSONFormatter(), TimestampConverter()]
        )

        self.quality_checker = Agent(
            role="Quality Assurance",
            goal="Ensure data meets quality standards",
            backstory="Meticulous QA specialist",
            tools=[SchemaValidator(), CompletenessChecker()]
        )

    @x402_required(
        price=UVD.amount("0.01"),
        pay_to=SELLER_WALLET,
        facilitator="https://facilitator.ultravioletadao.xyz"
    )
    async def get_logs(self, request: LogsRequest):
        """
        Main endpoint to sell logs.
        Payment verified by x402 middleware before executing.
        """
        # Query MongoDB
        logs = self.db.messages.find({
            "stream_id": request.stream_id,
            "timestamp": {
                "$gte": request.start_time,
                "$lte": request.end_time
            }
        }).limit(1000)

        # Format with CrewAI
        crew = Crew(
            agents=[self.data_formatter, self.quality_checker],
            tasks=[
                Task(
                    description=f"Format logs for stream {request.stream_id}",
                    agent=self.data_formatter
                ),
                Task(
                    description="Validate formatted data",
                    agent=self.quality_checker
                )
            ]
        )

        formatted_logs = crew.kickoff(inputs={"raw_logs": list(logs)})

        return {
            "stream_id": request.stream_id,
            "count": len(list(logs)),
            "logs": formatted_logs,
            "seller_agent_id": self.agent_id
        }

    def publish_agent_card(self):
        """Publish A2A AgentCard for discovery"""
        self.agent_card = AgentCard(
            agentId=self.agent_id,
            name="Karma-Hello Stream Logs Seller",
            description="Sells Twitch stream chat logs and events",
            version="1.0.0",
            skills=[
                Skill(
                    skillId="get_logs",
                    name="Get Stream Logs",
                    description="Retrieve chat logs for a stream with timestamps",
                    price={"amount": "0.01", "currency": "UVD"},
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "stream_id": {"type": "string"},
                            "start_time": {"type": "integer"},
                            "end_time": {"type": "integer"}
                        },
                        "required": ["stream_id"]
                    },
                    outputSchema={
                        "type": "object",
                        "properties": {
                            "logs": {"type": "array"},
                            "count": {"type": "integer"}
                        }
                    }
                )
            ],
            trustModels=["erc-8004"],
            paymentMethods=["x402-eip3009-UVD"]
        )

        # Serve at /.well-known/agent-card
        self.app.get("/.well-known/agent-card")(
            lambda: self.agent_card.dict()
        )
```

---

### 2. KarmaHelloBuyer (Client Agent)

**Rol**: Agente comprador que adquiere transcripciones de Abracadabra.

**Features**:
- ✅ A2A client para discovery
- ✅ EIP-712 signing para pagos
- ✅ Lógica de auto-compra inteligente
- ✅ Integración de datos comprados en MongoDB

**Lógica de Auto-Compra**:

```python
# Trigger: Detectar cuando un stream tiene logs pero NO transcripción

async def auto_buy_logic(self):
    """
    Busca streams que tengan logs pero les falta transcripción.
    Compra automáticamente de Abracadabra.
    """
    # Buscar streams sin transcripción
    streams_without_transcript = self.db.stream_sessions.find({
        "has_logs": True,
        "has_transcript": False
    })

    for stream in streams_without_transcript:
        # Discover Abracadabra seller
        abracadabra_card = await self.a2a_client.discover(
            "abracadabra-seller.ultravioletadao.xyz"
        )

        # Get price
        transcript_skill = abracadabra_card.get_skill("get_transcript")
        price = transcript_skill.price  # 0.02 UVD

        # Verificar balance
        balance = await self.check_uvd_balance()
        if balance < price.to_wei():
            logger.warning(f"Insufficient balance: {balance} < {price}")
            continue

        # Sign EIP-712 payment authorization
        auth = self.sign_transfer_authorization(
            from_=self.address,
            to=abracadabra_card.payment_address,
            value=price.to_wei(),
            valid_after=0,
            valid_before=int(time.time()) + 3600,
            nonce=self.generate_nonce()
        )

        # Make purchase
        try:
            response = await self.a2a_client.invoke_skill(
                agent_card=abracadabra_card,
                skill_id="get_transcript",
                params={
                    "stream_id": stream["stream_id"]
                },
                payment=auth
            )

            # Store transcript in DB
            self.db.transcripts.insert_one({
                "stream_id": stream["stream_id"],
                "transcript": response.data,
                "purchased_at": datetime.utcnow(),
                "price_paid": price.to_string(),
                "seller_agent_id": abracadabra_card.agentId
            })

            # Update stream session
            self.db.stream_sessions.update_one(
                {"stream_id": stream["stream_id"]},
                {"$set": {"has_transcript": True}}
            )

            logger.info(f"✅ Purchased transcript for {stream['stream_id']}")

        except Exception as e:
            logger.error(f"Failed to purchase: {e}")
```

---

## 🚀 Instalación

### Requisitos Previos

- Python 3.11+
- MongoDB (acceso al DB de karma-hello)
- Wallet con UVD tokens en Fuji
- Contratos ERC-8004 desplegados

### Instalación

```bash
cd z:\ultravioleta\dao\karmacadabra\karma-hello-agent

# Crear virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

**requirements.txt**:
```txt
web3==6.15.0
eth-account==0.11.0
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.6.0
pydantic-ai==0.0.7
crewai==0.28.0
pymongo==4.6.0
python-dotenv==1.0.0
aiohttp==3.9.0
```

---

## ⚙️ Configuración

### Archivo .env

```bash
cp .env.example .env
```

**Contenido de .env**:

```bash
# Network
RPC_URL=https://avalanche-fuji-c-chain-rpc.publicnode.com
CHAIN_ID=43113

# ERC-8004 Contracts
IDENTITY_REGISTRY=0x...
REPUTATION_REGISTRY=0x...
VALIDATION_REGISTRY=0x...

# UVD Token
UVD_TOKEN_ADDRESS=0x...

# x402 Facilitator
FACILITATOR_URL=https://facilitator.ultravioletadao.xyz

# Seller Agent
SELLER_PRIVATE_KEY=0x...
SELLER_DOMAIN=karma-hello-seller.ultravioletadao.xyz
SELLER_WALLET=0x...

# Buyer Agent
BUYER_PRIVATE_KEY=0x...
BUYER_WALLET=0x...

# MongoDB (karma-hello database)
MONGO_URI=mongodb://localhost:27017/karma_hello

# Validator
VALIDATOR_AGENT_ID=3

# CrewAI / OpenAI
OPENAI_API_KEY=sk-...

# Server
HOST=0.0.0.0
PORT=8081

# Logging
LOG_LEVEL=INFO
```

### config.yaml

```yaml
agent:
  seller:
    enabled: true
    port: 8081
    price_per_query: "0.01"  # UVD
    max_logs_per_query: 1000

  buyer:
    enabled: true
    auto_buy: true
    check_interval_seconds: 300  # 5 minutos
    max_budget_per_day: "1.0"  # UVD

database:
  collections:
    messages: "messages"
    user_activity: "user_activity"
    stream_sessions: "stream_sessions"
    transcripts: "transcripts"

crew_ai:
  model: "gpt-4o"
  temperature: 0.7
  max_iterations: 3

logging:
  level: "INFO"
  format: "json"
```

---

## 💻 Uso

### Registrar Agentes

```bash
# Registrar Seller
python scripts/register_seller.py

# Output:
# ✅ KarmaHelloSeller registered with ID: 1
# Domain: karma-hello-seller.ultravioletadao.xyz
# Address: 0x...

# Registrar Buyer
python scripts/register_buyer.py

# Output:
# ✅ KarmaHelloBuyer registered with ID: 4
# Address: 0x...
```

### Iniciar Seller API

```bash
# Modo producción
python main.py --mode seller

# Modo desarrollo
uvicorn main:app --reload --port 8081

# Output:
# INFO:     Started server process
# INFO:     Uvicorn running on http://0.0.0.0:8081
# ✅ KarmaHelloSeller listening...
# ✅ AgentCard published at /.well-known/agent-card
```

### Iniciar Buyer (Auto-Compra)

```bash
python main.py --mode buyer

# Output:
# ✅ KarmaHelloBuyer started
# 🔍 Checking for streams without transcripts...
# 📦 Found 3 streams to buy transcripts for
# 💰 Purchasing transcript for stream_12345...
# ✅ Purchase complete! Paid 0.02 UVD
```

---

## 📡 API

### AgentCard (A2A Discovery)

```http
GET /.well-known/agent-card
```

**Response**:
```json
{
  "agentId": 1,
  "name": "Karma-Hello Stream Logs Seller",
  "version": "1.0.0",
  "skills": [
    {
      "skillId": "get_logs",
      "name": "Get Stream Logs",
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
      }
    }
  ],
  "paymentMethods": ["x402-eip3009-UVD"],
  "trustModels": ["erc-8004"]
}
```

### Get Logs (Protected by x402)

```http
POST /api/logs
X-Payment: {"kind": "evm-eip3009-UVD", "payload": {...}}
Content-Type: application/json

{
  "stream_id": "12345",
  "start_time": 1730000000,
  "end_time": 1730003600
}
```

**Response (200 OK)**:
```json
{
  "stream_id": "12345",
  "count": 847,
  "logs": [
    {
      "timestamp": 1730000125,
      "user": "ultravioleta",
      "message": "¡Hola chat!",
      "badges": ["broadcaster"],
      "color": "#9146FF"
    },
    // ...
  ],
  "seller_agent_id": 1
}
```

**Sin pago (402 Payment Required)**:
```json
{
  "error": "Payment required",
  "accepts": [
    {
      "kind": "evm-eip3009-UVD",
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

---

## 🔗 Integración

### Comprar desde otro agente (Python)

```python
from a2a import A2AClient
from eip712 import EIP712Signer

# 1. Initialize client
client = A2AClient()
signer = EIP712Signer(private_key=BUYER_PRIVATE_KEY)

# 2. Discover
agent_card = await client.discover(
    "karma-hello-seller.ultravioletadao.xyz"
)

# 3. Sign payment
auth = signer.sign_transfer_authorization(
    from_=BUYER_WALLET,
    to=agent_card.payment_address,
    value=10000,  # 0.01 UVD
    valid_after=0,
    valid_before=int(time.time()) + 3600,
    nonce=generate_nonce()
)

# 4. Invoke skill
response = await client.invoke_skill(
    agent_card=agent_card,
    skill_id="get_logs",
    params={
        "stream_id": "12345",
        "start_time": 1730000000,
        "end_time": 1730003600
    },
    payment=auth
)

# 5. Use data
logs = response.data["logs"]
print(f"Received {len(logs)} messages")
```

---

## 📚 Estructura del Proyecto

```
karma-hello-agent/
├── README.md
├── SETUP.md
├── API.md
├── .env.example
├── config.yaml
├── requirements.txt
├── main.py                      # Entry point
├── agents/
│   ├── __init__.py
│   ├── base_agent.py            # ERC-8004 + A2A base
│   ├── karma_hello_seller.py    # Seller implementation
│   ├── karma_hello_buyer.py     # Buyer implementation
│   └── tools.py                 # CrewAI tools
├── scripts/
│   ├── register_seller.py
│   ├── register_buyer.py
│   └── test_integration.py
├── tests/
│   ├── test_seller.py
│   ├── test_buyer.py
│   └── test_payments.py
└── docs/
    └── ARCHITECTURE.md
```

---

## 🧪 Testing

```bash
# Unit tests
pytest tests/

# Integration tests
pytest tests/test_integration.py -v

# Test seller API
curl http://localhost:8081/.well-known/agent-card

# Test purchase (sin pago, debe retornar 402)
curl -X POST http://localhost:8081/api/logs \
  -H "Content-Type: application/json" \
  -d '{"stream_id": "12345"}'
```

---

## 📖 Documentación Adicional

- [SETUP.md](./SETUP.md) - Guía de setup detallada
- [API.md](./API.md) - Documentación completa de API
- [ARCHITECTURE.md](./docs/ARCHITECTURE.md) - Arquitectura interna
- [MASTER_PLAN.md](../MASTER_PLAN.md) - Plan maestro del ecosistema

---

**Desarrollado con ❤️ por Ultravioleta DAO**
