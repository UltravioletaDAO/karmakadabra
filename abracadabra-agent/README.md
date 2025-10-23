# 🎬 Abracadabra Agent System

> Agentes AI autónomos que comercializan transcripciones de streams usando ERC-8004 + A2A + x402

**Versión**: 1.0.0
**Network**: Avalanche Fuji Testnet
**Estado**: 🔴 Por implementar
**Última actualización**: Octubre 21, 2025

---

## 🗂️ Ubicación en el Proyecto

```
z:\ultravioleta\dao\karmacadabra\
├── erc-20/                    (GLUE Token - RECIBE pagos aquí)
├── erc-8004/                  (SE REGISTRA como Agent ID 2 y 5)
├── x402-rs/                   (USA facilitator para pagos)
├── validator/                 (SOLICITA validaciones antes de venta)
├── karma-hello-agent/         (COMPRA logs / VENDE transcripts)
├── abracadabra-agent/         ← ESTÁS AQUÍ
├── MASTER_PLAN.md
└── MONETIZATION_OPPORTUNITIES.md (VER productos completos aquí)
```

**Parte del Master Plan**: Phase 4 - Abracadabra Agents (Semana 5)

**Fuente de datos**: `z:\ultravioleta\ai\cursor\abracadabra\analytics.db` (SQLite + Cognee)

---

## 🎯 Descripción

El **Abracadabra Agent System** comercializa datos de transcripciones del sistema [abracadabra](z:\ultravioleta\ai\cursor\abracadabra).

### 💰 Productos que Vende (50+ servicios)

**Ver catálogo completo en**: `MONETIZATION_OPPORTUNITIES.md` § Abracadabra Servicios

**Tier 1** (0.02-0.08 UVD) - Datos de Transcripción:
- ✅ Raw Transcriptions (0.02 UVD)
- ✅ Enhanced Transcripts con topics (0.05 UVD)
- ✅ Multi-Language Transcripts (0.08 UVD) - 10 idiomas

**Tier 2** (0.10-0.25 UVD) - Content Intelligence:
- ✅ Clip Generation Service - 0.15 UVD
- ✅ Blog Post Generation (4 estilos) - 0.20 UVD
- ✅ Social Media Package - 0.18 UVD
- ✅ Insights Engine - 0.22 UVD

**Tier 3** (0.25-0.50 UVD) - Advanced Analytics:
- ✅ Predictive Engine (LSTM forecasting) - 0.35 UVD
- ✅ Recommendation System - 0.30 UVD
- ✅ Knowledge Graph Search (640+ topics) - 0.25 UVD

**Tier 4** (0.50-2.00 UVD) - Production Services:
- ✅ Automated Video Editing - 1.50 UVD
- ✅ Image Generation (20 imágenes DALL-E 3) - 0.80 UVD
- ✅ Auto Publishing System - 0.60 UVD/post

**Tier 5** (0.80-3.00 UVD) - AI-Powered Analysis:
- ✅ Deep Idea Extraction - 1.20 UVD
- ✅ Audio Analysis Suite - 0.90 UVD
- ✅ Advanced A/B Testing (Bayesian) - 2.00 UVD

**Tier 6** (Custom Pricing) - Enterprise:
- Multi-Stream Aggregation (10-50 UVD)
- Team Management Suite (25 UVD + 10 UVD/mes)
- Custom AI Model Training (100 UVD)

**Total**: 30+ servicios comercializables

### Datos Disponibles

Abracadabra procesa streams con (`z:\ultravioleta\ai\cursor\abracadabra`):
- **Transcripciones completas** (AWS Transcribe + Whisper)
- **Segmentos con timestamps** precisos por palabra
- **Topics extraídos** con GPT-4o (640+ topics en Cognee)
- **Entidades** (personas, lugares, productos, tecnologías)
- **Sentiment analysis** (7 categorías de emociones)
- **Knowledge graph** (Cognee con semantic search)
- **Analytics** (engagement scoring, coherence, quality metrics)
- **Images** (20 generadas con DALL-E 3 + Computer Vision scoring)
- **Clips** (auto-detected highlights con timestamps)
- **Ideas** (5 ideas extraídas con brainstorming completo)

### Problema que Resuelve

Karma-Hello tiene **logs del chat**, pero NO sabe:
- ¿Qué dijo el streamer en ese momento?
- ¿De qué estaba hablando?
- ¿Qué topic estaba cubriendo?
- ¿Cómo se relaciona con lo que dijo el chat?

**Solución**: Comprar transcripciones de Abracadabra para relacionar logs del chat con contenido de audio.

### 🛒 Productos que Compra

**Abracadabra Buyer** compra de Karma-Hello:
- ✅ Chat Logs (0.01 UVD)
- ✅ User Activity (0.02 UVD)
- ✅ Token Economics Data (0.03 UVD)

**Caso de uso**: Relacionar transcripciones con lo que decía el chat en tiempo real.

---

## 📂 Estructura de Datos - PRODUCTOS A VENDER

### Ubicación Local de Productos

```
z:\ultravioleta\dao\karmacadabra\abracadabra-agent\
├── transcripts/                       ← PRODUCTOS AQUÍ
│   ├── 20251013/
│   ├── 20251014/
│   ├── 20251015/
│   ├── 20251016/
│   ├── 20251017/
│   ├── 20251020/                     # Ejemplo actual
│   │   └── 2596913801/               # Stream ID
│   │       ├── audio_2596913801.mp3  # 127MB - Audio original
│   │       ├── transcripcion.json    # 3.3MB - ✅ PRODUCTO PRINCIPAL
│   │       ├── ideas_extraidas.json  # 21KB - ✅ Ideas + brainstorming
│   │       ├── processing_status.json # 5KB - Metadata
│   │       ├── titulo_stream.txt     # Título del stream
│   │       │
│   │       ├── resumen_completo.txt  # 3.8KB - ✅ Resumen técnico
│   │       ├── analisis_completo.txt # 6.7KB - ✅ Análisis profundo
│   │       ├── resumen_telegram.txt  # 2.9KB - ✅ Resumen corto
│   │       ├── tweet.txt             # 318B - ✅ Tweet generado
│   │       ├── analisis_critico_marketing.txt # 2.1KB
│   │       ├── descripcion_seo_twitch.txt     # 463B
│   │       │
│   │       ├── segmentos/            # ✅ Clips detectados
│   │       │   └── [timestamps + metadata]
│   │       │
│   │       ├── imagenes_generadas/   # ✅ 20 imágenes DALL-E 3
│   │       │   ├── imagen_0.png
│   │       │   ├── imagen_1.png
│   │       │   └── [18 imágenes más...]
│   │       │
│   │       ├── prompts_imagen/       # Prompts para DALL-E
│   │       ├── prompts_video/        # Prompts para clips
│   │       ├── resumenes_para_youtube/
│   │       └── resumenes_web/
│   └── README.md
└── .env.example
```

### Productos Clave por Archivo

**1. `transcripcion.json`** (3.3MB) - PRODUCTO PRINCIPAL
```json
{
  "stream_id": "2596913801",
  "duration": 10800,  // 3 horas
  "segments": [
    {
      "timestamp": 125.5,
      "text": "Hoy vamos a programar un smart contract...",
      "confidence": 0.98,
      "speaker": "streamer"
    }
  ],
  "topics": [
    {
      "tipo": "arquitectura",
      "idea": "Migración AWS a Cherry Servers",
      "tecnologias": ["AWS", "Docker", "Kubernetes"],
      "prioridad": 8
    },
    {
      "tipo": "nuevo_proyecto",
      "idea": "Convertirse en facilitador X-402",
      "tecnologias": ["X-402", "FastAPI"],
      "timeline": "mañana"
    }
  ],
  "entities": {
    "personas": ["0xultravioleta"],
    "tecnologias": ["AWS", "Cherry Servers", "X-402", "ERC-8004"],
    "proyectos": ["UltravioletaDao Facilitator"]
  }
}
```

**2. `ideas_extraidas.json`** (21KB) - 5 IDEAS CON BRAINSTORMING
```json
{
  "ideas": [
    {
      "idea_original": "Convertirse en facilitador X-402",
      "tecnologias": ["X-402", "FastAPI", "Node.js"],
      "complejidad": "moderada",
      "impacto_estimado": "alto",
      "prioridad_sugerida": 8,
      "roi_estimado": "Alto, creciente interés en protocolos de verificación",
      "proximos_pasos": [
        "Contactar desarrolladores X-402",
        "Desarrollar prototipo básico"
      ]
    }
  ]
}
```

**3. `imagenes_generadas/`** - 20 IMÁGENES DALL-E 3
- Computer Vision scoring de calidad
- Color palette extraction (k-means)
- Composition scoring
- Brightness/contrast analysis

**4. Content Generation**:
- `resumen_completo.txt` - Blog post técnico
- `tweet.txt` - Tweet optimizado
- `analisis_critico_marketing.txt` - Análisis de marketing
- `resumenes_para_youtube/` - Descripciones para YouTube

### Fuente Original (SQLite + Cognee)

**Producción**: `z:\ultravioleta\ai\cursor\abracadabra\analytics.db` (SQLite)

**Tablas**:
- `transcripts` - Transcripciones completas
- `segments` - Segmentos con timestamps
- `topics` - Topics extraídos (640+ topics)
- `entities` - Entidades mencionadas
- `analytics` - Métricas de engagement

**Cognee Knowledge Graph**: 640+ topics indexados con embeddings

**Nota**: Los archivos en `abracadabra-agent/transcripts/` son **copias exportadas** para testing. El agente en producción consultará SQLite + Cognee.

### CrewAI Agent: Dónde Buscar Datos

```python
# En abracadabra_seller.py

class AbracadabraSeller(ERC8004BaseAgent):
    def __init__(self, config):
        # OPCIÓN 1: Desarrollo/Testing - Leer archivos locales
        self.transcripts_path = "z:\\ultravioleta\\dao\\karmacadabra\\abracadabra-agent\\transcripts"

        # OPCIÓN 2: Producción - SQLite + Cognee
        self.db_path = config.SQLITE_DB_PATH  # z:\ultravioleta\ai\cursor\abracadabra\analytics.db
        self.db = sqlite3.connect(self.db_path)
        self.cognee = CogneeClient()

    async def get_transcript(self, stream_id: str, enhanced: bool = False):
        # TESTING: Leer de archivos locales
        if config.USE_LOCAL_FILES:
            # Buscar en transcripts/YYYYMMDD/{stream_id}/
            transcript_file = self._find_transcript_file(stream_id)

            with open(f"{transcript_file}/transcripcion.json", 'r') as f:
                transcript = json.load(f)

            if enhanced:
                # Incluir ideas, resúmenes, imágenes
                with open(f"{transcript_file}/ideas_extraidas.json", 'r') as f:
                    transcript["ideas"] = json.load(f)

                # Listar imágenes generadas
                images_dir = f"{transcript_file}/imagenes_generadas"
                transcript["images"] = os.listdir(images_dir)

            return transcript

        # PRODUCCIÓN: Query SQLite + Cognee
        else:
            transcript = self.db.execute(
                "SELECT * FROM transcripts WHERE stream_id = ?",
                (stream_id,)
            ).fetchone()

            if enhanced:
                # Buscar topics en Cognee knowledge graph
                topics = await self.cognee.search(transcript["text"])
                transcript["topics"] = topics

            return transcript

    def _find_transcript_file(self, stream_id: str):
        """Busca el stream_id en todas las fechas"""
        for date_folder in os.listdir(self.transcripts_path):
            stream_path = f"{self.transcripts_path}/{date_folder}/{stream_id}"
            if os.path.exists(stream_path):
                return stream_path
        raise FileNotFoundError(f"Stream {stream_id} not found")
```

### Servicios Disponibles por Archivo

| Archivo/Carpeta | Servicio | Tier | Precio |
|----------------|----------|------|--------|
| `transcripcion.json` | Raw Transcript | 1 | 0.02 UVD |
| `transcripcion.json` + topics | Enhanced Transcript | 1 | 0.05 UVD |
| `ideas_extraidas.json` | Deep Idea Extraction | 5 | 1.20 UVD |
| `imagenes_generadas/` | Image Generation Service | 4 | 0.80 UVD |
| `resumen_completo.txt` | Blog Post Generation | 2 | 0.20 UVD |
| `tweet.txt` | Social Media Package | 2 | 0.18 UVD |
| `segmentos/` | Clip Generation | 2 | 0.15 UVD |
| Cognee search | Knowledge Graph Search | 3 | 0.25 UVD |

**Total productos en un stream**: 8+ servicios comercializables

---

## 🤖 Agentes

### 1. AbracadabraSeller (Server Agent)

**Endpoint**: `POST /api/transcripts`
**Precio**: 0.02 UVD por transcripción

**Implementación clave**:
```python
from agents.base_agent import ERC8004BaseAgent
from a2a import A2AServer
import sqlite3
from cognee import CogneeClient

class AbracadabraSeller(ERC8004BaseAgent, A2AServer):
    def __init__(self, config):
        super().__init__(
            agent_domain="abracadabra-seller.ultravioletadao.xyz",
            private_key=config.SELLER_PRIVATE_KEY
        )

        # SQLite analytics DB
        self.db = sqlite3.connect(config.SQLITE_DB_PATH)

        # Cognee knowledge graph
        self.cognee = CogneeClient()

        self.agent_id = self.register_agent()
        self.publish_agent_card()

    @x402_required(price=UVD.amount("0.02"))
    async def get_transcript(self, request: TranscriptRequest):
        # Query SQLite
        transcript = self.db.execute(
            "SELECT * FROM transcripts WHERE stream_id = ?",
            (request.stream_id,)
        ).fetchone()

        # Enrich with Cognee topics
        topics = await self.cognee.search(transcript.text)

        # Format with CrewAI
        crew = Crew(agents=[self.enricher, self.analyzer])
        result = crew.kickoff(inputs={
            "transcript": transcript,
            "topics": topics
        })

        return TranscriptResponse(data=result)
```

### 2. AbracadabraBuyer (Client Agent)

**Lógica**: Compra logs de Karma-Hello cuando detecta menciones sin contexto del chat.

```python
async def auto_buy_logic(self):
    # Buscar transcripciones con menciones a usuarios
    transcripts_with_mentions = self.db.execute("""
        SELECT * FROM transcripts
        WHERE text LIKE '%@%'
        AND has_chat_logs = FALSE
    """).fetchall()

    for transcript in transcripts_with_mentions:
        # Buy logs from Karma-Hello
        karma_card = await self.a2a_client.discover(
            "karma-hello-seller.ultravioletadao.xyz"
        )

        response = await self.buy_logs(
            karma_card,
            stream_id=transcript.stream_id
        )

        # Enrich knowledge graph
        await self.cognee.add_relation(
            transcript_id=transcript.id,
            logs=response.data
        )
```

---

## 📡 API

### AgentCard
```http
GET /.well-known/agent-card
```

### Get Transcript (Protected by x402)
```http
POST /api/transcripts
X-Payment: {"kind": "evm-eip3009-UVD", "payload": {...}}

{
  "stream_id": "12345",
  "include_topics": true,
  "include_entities": true
}
```

**Response**:
```json
{
  "stream_id": "12345",
  "transcript": {
    "text": "Hoy vamos a programar un smart contract...",
    "segments": [
      {
        "timestamp": 1730000125.5,
        "text": "Hoy vamos a programar",
        "confidence": 0.98
      }
    ],
    "topics": ["smart contracts", "solidity", "blockchain"],
    "entities": ["Ethereum", "Solidity", "Foundry"],
    "sentiment": {
      "overall": "positive",
      "score": 0.85
    }
  },
  "seller_agent_id": 2
}
```

---

## ⚙️ Configuración

**.env**:
```bash
# SQLite Database
SQLITE_DB_PATH=z:\ultravioleta\ai\cursor\abracadabra\analytics.db

# Cognee
COGNEE_API_KEY=...
COGNEE_LLM_MODEL=gpt-4o

# Agent
SELLER_PRIVATE_KEY=0x...
SELLER_DOMAIN=abracadabra-seller.ultravioletadao.xyz
SELLER_WALLET=0x...

# Buyer
BUYER_PRIVATE_KEY=0x...
BUYER_WALLET=0x...
```

---

## 🚀 Uso

```bash
# Install
pip install -r requirements.txt

# Register
python scripts/register_seller.py

# Run seller
python main.py --mode seller --port 8082

# Run buyer
python main.py --mode buyer
```

---

## 📚 Estructura

```
abracadabra-agent/
├── README.md
├── agents/
│   ├── abracadabra_seller.py
│   ├── abracadabra_buyer.py
│   └── base_agent.py
├── scripts/
│   ├── register_seller.py
│   └── register_buyer.py
├── requirements.txt
├── .env.example
└── main.py
```

---

**Ver [MASTER_PLAN.md](../MASTER_PLAN.md) para más detalles del ecosistema.**
