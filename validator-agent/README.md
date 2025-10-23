# 🔍 Validator Agent (Bob)

> Agente validador independiente que verifica la calidad de datos antes de cada transacción

**Versión**: 1.0.0
**Network**: Avalanche Fuji Testnet
**Basado en**: Bob del ejemplo ERC-8004
**Estado**: 🔴 Por implementar
**Última actualización**: Octubre 21, 2025

---

## 🗂️ Ubicación en el Proyecto

```
z:\ultravioleta\dao\karmacadabra\
├── erc-20/                    (GLUE Token - recibe 0.001 GLUE por validación)
├── erc-8004/                  (REGISTRA identidad aquí, SUBE validaciones)
├── x402-rs/                   (x402 Facilitator)
├── validator/                 ← ESTÁS AQUÍ
├── karma-hello-agent/         (VALIDA sus logs antes de venta)
├── abracadabra-agent/         (VALIDA sus transcripts antes de venta)
├── MASTER_PLAN.md            (Plan completo del proyecto)
└── MONETIZATION_OPPORTUNITIES.md
```

**Parte del Master Plan**: Phase 2 - Base Agents (Semana 3)

---

## 🎯 Descripción

El **Validator Agent** es un agente neutral que valida la calidad de datos en transacciones entre Karma-Hello y Abracadabra.

### ¿Por qué un Validator?

**Problema**: Buyers pagan por datos que podrían ser de baja calidad.

**Solución**: Validator independiente verifica calidad ANTES del pago, proporcionando un score de 0-100. Los buyers pueden rechazar si el score es bajo.

### Rol en el Ecosistema

**El Validator NO vende datos**, solo proporciona un servicio:

**Servicio**:
- ✅ **Validación de calidad de datos** (0.001 UVD por validación)
- ✅ **Fraud detection** como servicio premium (ver MONETIZATION Tier 3)
- ✅ **Compliance audit trail** para DAOs/protocolos

**Clientes del Validator**:
- **Karma-Hello Seller**: Valida sus logs antes de venderlos (aumenta confianza)
- **Abracadabra Seller**: Valida sus transcripts antes de venderlos
- **Buyers**: Consultan validaciones on-chain antes de pagar
- **DAOs/Protocolos**: Contratan validaciones para compliance (ver MONETIZATION)

**Ingresos proyectados**:
- Si valida 100 transacciones/día: 0.1 UVD/día = 36.5 UVD/año
- Si ofrece Fraud Detection premium (0.20 UVD): +revenue adicional
- Ver `MONETIZATION_OPPORTUNITIES.md` § Tier 3 "Fraud Detection Service"

### Fees y Costos

**Ingresos (UVD recibido)**:
- **0.001 UVD** por validación básica (pagado por el buyer)
- **0.20 UVD** por Fraud Detection Service (servicio premium)

**Gastos (AVAX pagado)**:
- **~0.01 AVAX** por cada transacción `validationResponse()` on-chain
- ⚠️ **IMPORTANTE**: Validator es el ÚNICO agente que paga gas (los demás usan EIP-3009 gasless)

**Economía del Validator**:
```
Fee actual:     0.001 UVD por validación
Gas cost:       ~0.01 AVAX por validación
Rentabilidad:   ❌ NO rentable en testnet (gas > fee)

Soluciones:
1. Aumentar VALIDATION_FEE_UVD a 0.01+ UVD
2. Usar Layer 2 para reducir gas
3. Batch validations (validar múltiples en una tx)
```

**Reputación on-chain** basada en accuracy (cuántas validaciones fueron correctas)

---

## 🏗️ Arquitectura

### Interacción con Blockchain

```
┌────────────────────────────────────────────────────┐
│         AVALANCHE FUJI TESTNET                     │
│                                                    │
│  ┌──────────────────────────────────────────┐     │
│  │   ValidationRegistry (Smart Contract)    │     │
│  │                                          │     │
│  │   validationRequest(validator, seller,   │     │
│  │                     dataHash)            │ ◄── Buyer llama
│  │   ✓ Registra request on-chain           │     │
│  │                                          │     │
│  │   validationResponse(dataHash, score)    │ ◄── ❗VALIDATOR ESCRIBE❗
│  │   ✓ Requiere AVAX para gas (~0.01)       │     │
│  │   ✓ Guarda score 0-100 on-chain          │     │
│  │   ✓ Emite event ValidationResponseEvent  │     │
│  │                                          │     │
│  │   getValidationResponse(dataHash)        │     │
│  │   ✓ Lectura gratis (no gas)              │     │
│  └──────────────────────────────────────────┘     │
└────────────────────────────────────────────────────┘
                      ▲
                      │ web3.py
                      │ Validator.send_transaction()
                      │ PAGA GAS AQUÍ
                      │
┌─────────────────────┴──────────────────────────────┐

```
┌─────────────────────────────────────────────┐
│          Validator Agent (Bob)              │
├─────────────────────────────────────────────┤
│                                             │
│  • ERC-8004 Agent ID: 3                     │
│  • Domain: validator.ultravioletadao.xyz    │
│  • Role: Independent validator              │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │   CrewAI Validation Crew            │   │
│  ├─────────────────────────────────────┤   │
│  │                                     │   │
│  │  Agent 1: Quality Analyst           │   │
│  │  • Verifica completeness            │   │
│  │  • Valida schemas                   │   │
│  │  • Chequea timestamps               │   │
│  │                                     │   │
│  │  Agent 2: Fraud Detector            │   │
│  │  • Detecta duplicados               │   │
│  │  • Verifica autenticidad            │   │
│  │  • Similarity checks                │   │
│  │                                     │   │
│  │  Agent 3: Price Reviewer            │   │
│  │  • Verifica que precio es justo     │   │
│  │  • Market comparison                │   │
│  │  • Historical data                  │   │
│  │                                     │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  Output: Validation Score (0-100)           │
│          + Detailed Report                  │
└─────────────────────────────────────────────┘
```

---

## 🤖 Implementación

### Basado en Bob

```python
# Extraído de z:\erc8004\erc-8004-example\agents\validator_agent.py

from agents.base_agent import ERC8004BaseAgent
from crewai import Agent, Task, Crew

class ValidatorAgent(ERC8004BaseAgent):
    def __init__(self, config):
        super().__init__(
            agent_domain="validator.ultravioletadao.xyz",
            private_key=config.VALIDATOR_PRIVATE_KEY
        )

        self.agent_id = self.register_agent()
        self.setup_validation_crew()

    def setup_validation_crew(self):
        self.quality_analyst = Agent(
            role="Data Quality Analyst",
            goal="Verify data completeness and format",
            backstory="Expert in data validation with 15+ years experience",
            tools=[CheckSchema(), VerifyTimestamps(), ValidateJSON()]
        )

        self.fraud_detector = Agent(
            role="Fraud Detection Specialist",
            goal="Detect fake or duplicate data",
            backstory="Forensic data analyst specialized in fraud detection",
            tools=[SimilarityCheck(), BlockchainVerify(), DuplicateDetector()]
        )

        self.price_reviewer = Agent(
            role="Price Fairness Reviewer",
            goal="Ensure pricing is fair and competitive",
            backstory="Market analyst with knowledge of data pricing",
            tools=[MarketCheck(), HistoricalPrices(), FairnessCalculator()]
        )

    async def validate_transaction(self,
                                   data_hash: str,
                                   seller_id: int,
                                   buyer_id: int,
                                   data_type: str) -> ValidationResult:
        """
        Valida una transacción de datos.

        Args:
            data_hash: Hash de los datos a validar
            seller_id: ID del agente vendedor
            buyer_id: ID del agente comprador
            data_type: 'logs' o 'transcript'
        """
        # 1. Cargar datos
        data = await self.load_data(data_hash)

        # 2. Ejecutar crew de validación
        crew = Crew(
            agents=[
                self.quality_analyst,
                self.fraud_detector,
                self.price_reviewer
            ],
            tasks=[
                Task(
                    description=f"Analyze data quality for {data_type}",
                    agent=self.quality_analyst
                ),
                Task(
                    description="Check for fraud indicators",
                    agent=self.fraud_detector
                ),
                Task(
                    description="Review price fairness",
                    agent=self.price_reviewer
                )
            ]
        )

        validation_report = crew.kickoff(inputs={
            "data": data,
            "data_type": data_type,
            "seller_id": seller_id,
            "buyer_id": buyer_id
        })

        # 3. Extraer score (0-100)
        score = self.extract_score(validation_report)

        # 4. Submit on-chain
        tx_hash = await self.submit_validation_response(
            data_hash=bytes.fromhex(data_hash),
            response=score
        )

        return ValidationResult(
            score=score,
            report=validation_report,
            tx_hash=tx_hash,
            validator_id=self.agent_id
        )
```

---

## ✅ Criterios de Validación

### Para Logs (Karma-Hello)

```python
def validate_logs(self, logs_data):
    checks = {
        "timestamps_valid": all(
            0 < log["timestamp"] < time.time()
            for log in logs_data
        ),
        "users_exist": all(
            self.verify_twitch_user(log["user"])
            for log in logs_data
        ),
        "no_duplicates": len(logs_data) == len(set(
            log["timestamp"] + log["user"] + log["message"]
            for log in logs_data
        )),
        "valid_json": self.validate_schema(logs_data, LOGS_SCHEMA),
        "messages_not_empty": all(
            len(log["message"]) > 0
            for log in logs_data
        )
    }

    score = sum(checks.values()) / len(checks) * 100
    return score, checks
```

### Para Transcripts (Abracadabra)

```python
def validate_transcript(self, transcript_data):
    checks = {
        "audio_exists": self.verify_stream_exists(
            transcript_data["stream_id"]
        ),
        "coherence": self.check_text_coherence(
            transcript_data["text"]
        ),
        "timestamps_match": self.verify_duration(
            transcript_data["segments"]
        ),
        "not_random": self.detect_gibberish(
            transcript_data["text"]
        ),
        "topics_relevant": self.verify_topics(
            transcript_data["topics"],
            transcript_data["text"]
        )
    }

    score = sum(checks.values()) / len(checks) * 100
    return score, checks
```

---

## 📡 API

### Request Validation (From Seller)

```python
# Seller solicita validación antes de vender
validator = ValidatorAgent.get_by_id(VALIDATOR_ID)

validation = await validator.validate_transaction(
    data_hash="0xabc123...",
    seller_id=1,  # KarmaHelloSeller
    buyer_id=4,   # KarmaHelloBuyer
    data_type="logs"
)

# Validation result
{
  "score": 95,
  "report": "Data quality: EXCELLENT. All checks passed...",
  "tx_hash": "0xdef456...",
  "validator_id": 3
}
```

### Query Validation (From Buyer)

```python
# Buyer consulta validación antes de pagar
validation_score = await identity_registry.get_validation_score(
    data_hash="0xabc123..."
)

if validation_score >= 80:
    # Proceder con compra
    await buyer.purchase(data_hash)
else:
    # Rechazar
    logger.warning(f"Low quality: {validation_score}/100")
```

---

## ⚙️ Configuración

**.env**:
```bash
# Validator
VALIDATOR_PRIVATE_KEY=0x...
VALIDATOR_DOMAIN=validator.ultravioletadao.xyz
VALIDATOR_WALLET=0x...

# Validation fee
VALIDATION_FEE_UVD=0.001

# CrewAI
OPENAI_API_KEY=sk-...
CREW_MODEL=gpt-4o

# ERC-8004
VALIDATION_REGISTRY=0x...
```

---

## 🚀 Uso

```bash
# Install
pip install -r requirements.txt

# Register
python scripts/register_validator.py

# Run
python main.py

# Output:
# ✅ Validator Agent listening...
# 🔍 Waiting for validation requests...
```

---

## 📊 Reputación On-Chain

El Validator construye reputación basado en:
- **Accuracy**: ¿Sus validaciones fueron correctas?
- **Response time**: ¿Qué tan rápido responde?
- **Ratings**: Buyers y sellers pueden calificarlo

```solidity
// ValidationRegistry.sol

function rateValidator(uint256 validatorId, uint256 rating) external {
    require(rating <= 100, "Max rating is 100");
    // Store rating on-chain
}

function getValidatorReputation(uint256 validatorId)
    external view returns (uint256) {
    // Return average rating
}
```

---

## 📚 Estructura

```
validator/
├── README.md                   # ← Este archivo
├── agents/
│   ├── base_agent.py          # Hereda de ERC8004BaseAgent
│   ├── validator_agent.py     # Main logic (basado en Bob)
│   └── validation_tools.py    # CrewAI tools
├── scripts/
│   └── register_validator.py  # Registra en ERC-8004
├── requirements.txt
├── .env.example
└── main.py                     # Entry point
```

**Productos que Valida**:
- Karma-Hello logs (ver `karma-hello-agent/` para formato de datos)
- Abracadabra transcripts (ver `abracadabra-agent/` para formato)

**Fuentes de datos para validación**:
- MongoDB: `z:\ultravioleta\ai\cursor\karma-hello` (para verificar logs)
- SQLite: `z:\ultravioleta\ai\cursor\abracadabra\analytics.db` (para verificar transcripts)

---

## 🔗 Referencias

- **Ejemplo Original (Bob)**: `z:\erc8004\erc-8004-example\agents\validator_agent.py`
- **MASTER_PLAN.md**: Flujo completo de validación
- **MONETIZATION_OPPORTUNITIES.md**: Servicios premium (Fraud Detection, Compliance)

---

**Ver [MASTER_PLAN.md](../MASTER_PLAN.md) para el flujo completo.**
