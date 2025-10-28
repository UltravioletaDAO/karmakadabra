# Transaction Logging System - Karmacadabra

## 📝 Resumen

Sistema de marcado de transacciones en blockchain que registra **todas las transacciones de agentes** con mensajes UTF-8 legibles que aparecen **permanentemente** en Snowtrace.

**Inspirado por:** Sistema de logging de Karma-Hello (@karmahelloapp)

---

## 🎯 Propósito

Cada transacción en la economía de agentes queda documentada en el blockchain de Avalanche Fuji con:
- **Mensaje descriptivo** en UTF-8 (legible para humanos)
- **Participantes** claramente identificados (buyer, seller, validator)
- **Propósito** de la transacción (servicio comprado/vendido)
- **Monto** en GLUE
- **Timestamp** inmutable

**Resultado:** Transparencia total y trazabilidad eterna de todas las interacciones entre agentes.

---

## 📍 Contratos Desplegados

### TransactionLogger Contract
- **Address:** `0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654`
- **Network:** Avalanche Fuji Testnet (Chain ID: 43113)
- **Snowtrace:** https://testnet.snowtrace.io/address/0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654
- **Status:** ✅ Deployed and Verified

---

## 🔧 Funcionalidad

### 1. Log de Pagos entre Agentes

Cada pago entre agentes emite un evento `AgentPayment` con formato:

```
Payment via Karmacadabra by Ultravioleta DAO | {from_agent} → {to_agent} | {amount} GLUE for {service}
```

**Ejemplo:**
```
Payment via Karmacadabra by Ultravioleta DAO | client-agent → karma-hello-agent | 0.010000 GLUE for Chat Logs - Full Day 2025-10-21
```

### 2. Log de Validaciones

Cada validación emite un evento `ValidationLogged` con formato:

```
Validation via Karmacadabra by Ultravioleta DAO | Validator: {validator_address} | Target: {target_address} | Score: {score}/100 | {details}
```

**Ejemplo:**
```
Validation via Karmacadabra by Ultravioleta DAO | Validator: 0x1219eF9484... | Target: 0x2C3e071df4... | Score: 95/100 | High quality chat logs - Well formatted, complete timestamps
```

### 3. Eventos Emitidos

#### TransactionLogged
```solidity
event TransactionLogged(
    address indexed agent,
    bytes32 indexed txHash,
    string message,
    uint256 timestamp
);
```

#### AgentPayment
```solidity
event AgentPayment(
    address indexed from,
    address indexed to,
    uint256 amount,
    string service,
    string message
);
```

#### ValidationLogged
```solidity
event ValidationLogged(
    address indexed validator,
    address indexed target,
    uint256 score,
    string message
);
```

---

## 💻 Uso en Python

### Setup

```python
from shared.transaction_logger import TransactionLogger

# Inicializar logger para un agente
logger = TransactionLogger(
    agent_private_key="0x...",
    agent_name="karma-hello-agent"
)
```

### Ejemplo 1: Logging de Pago

```python
# Después de recibir/enviar un pago vía EIP-3009
result = logger.log_payment(
    payment_tx_hash="0x123...",           # TX hash del pago GLUE
    from_agent="client-agent",            # Nombre del comprador
    to_agent="karma-hello-agent",         # Nombre del vendedor
    amount_glue=0.01,                     # Cantidad en GLUE
    service="Chat Logs for 2025-10-21",   # Descripción del servicio
    from_address="0xCf30021...",          # Address del comprador
    to_address="0x2C3e071..."             # Address del vendedor
)

print(f"Payment logged: {result['log_tx']}")
# Output: https://testnet.snowtrace.io/tx/0xabc...
```

### Ejemplo 2: Logging de Validación

```python
# Después de validar datos
result = logger.log_validation(
    validation_tx_hash="0x456...",
    target_address="0x2C3e071...",
    score=95,  # 0-100
    details="High quality data - well formatted"
)

print(f"Validation logged: {result['log_tx']}")
```

### Ejemplo 3: Leer Mensajes Existentes

```python
# Obtener el mensaje de una transacción
message = logger.get_message("0x123...")
print(message)
# Output: "Payment via Karmacadabra by Ultravioleta DAO | ..."
```

---

## 🔄 Flujo Completo de Transacción con Logging

### Escenario: Client Agent compra logs de Karma-Hello Agent

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CLIENT FIRMA AUTORIZACIÓN DE PAGO (EIP-3009)            │
│    - Firma off-chain: transferWithAuthorization             │
│    - Amount: 0.01 GLUE                                      │
│    - Nonce: random para evitar replay                       │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. CLIENT ENVÍA REQUEST A KARMA-HELLO                       │
│    - HTTP POST /api/logs                                    │
│    - Header: X-Payment (firma EIP-3009)                     │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. FACILITATOR EJECUTA PAGO (GASLESS)                       │
│    - Verifica firma EIP-712                                 │
│    - Ejecuta transferWithAuthorization()                    │
│    - TX hash: 0x123...                                      │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. KARMA-HELLO RETORNA DATOS                                │
│    - Envía chat logs al client                              │
│    - Client recibe datos                                    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. AMBOS AGENTES LOGUEAN LA TRANSACCIÓN                     │
│    - Client: logger.log_payment(0x123..., ...)              │
│    - Karma-Hello: logger.log_payment(0x123..., ...)         │
│    - Eventos emitidos en blockchain                         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. LOGS PERMANENTES EN SNOWTRACE                            │
│    - Payment TX visible                                     │
│    - 2 log events visibles                                  │
│    - Mensajes UTF-8 legibles                                │
│    - Trazabilidad eterna                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Tipos de Transacciones Logueadas

### Sistema Karmacadabra

| From | To | Service | Precio GLUE | Mensaje Ejemplo |
|------|----|---------|-----------|--------------------|
| Client | Karma-Hello | Chat Logs | 0.01 | `client-agent → karma-hello-agent \| 0.01 GLUE for Chat Logs` |
| Client | Abracadabra | Transcript | 0.02 | `client-agent → abracadabra-agent \| 0.02 GLUE for Stream Transcript` |
| Client | Validator | Validation | 0.001 | `client-agent → validator-agent \| 0.001 GLUE for Data Validation` |
| Karma-Hello | Voice-Extractor | Voice Profile | 0.04 | `karma-hello-agent → voice-extractor-agent \| 0.04 GLUE for Voice Profile` |
| Karma-Hello | Skill-Extractor | Skill Profile | 0.05 | `karma-hello-agent → skill-extractor-agent \| 0.05 GLUE for Skill Profile` |

**Total:** Cada transacción = 2 logs (comprador + vendedor) + 1 pago = **trazabilidad completa**

---

## 🎨 Visualización en Snowtrace

Cuando visitas Snowtrace, verás:

### Tab "Events"
```
AgentPayment
├─ from: 0xCf30021... (client-agent)
├─ to: 0x2C3e071... (karma-hello-agent)
├─ amount: 10000 (0.01 GLUE with 6 decimals)
├─ service: "Chat Logs for 2025-10-21"
└─ message: "Payment via Karmacadabra by Ultravioleta DAO | client-agent → karma-hello-agent | 0.010000 GLUE for Chat Logs for 2025-10-21"
```

### Tab "Logs"
```
TransactionLogged
├─ agent: 0xCf30021...
├─ txHash: 0x123...
├─ message: "Payment via Karmacadabra..."
└─ timestamp: 1729680932
```

---

## 🚀 Beneficios

### 1. Transparencia Total
- Todas las transacciones visibles públicamente
- Mensajes en lenguaje natural (no solo hex)
- Trazabilidad completa de la economía de agentes

### 2. Auditoría Eterna
- Logs inmutables en blockchain
- No se pueden borrar ni modificar
- Historial completo desde el inicio

### 3. Debugging Facilitado
- Mensajes descriptivos ayudan a debuggear
- Identificación clara de problemas
- Timeline completo de eventos

### 4. Reputación Verificable
- Historial de transacciones de cada agente
- Proof of work on-chain
- Transparencia para usuarios

### 5. Compatibilidad con Análisis
- Eventos indexables
- Queries fáciles via The Graph
- Dashboards en tiempo real

---

## 📝 Integración en Base Agent

El `base_agent.py` incluirá automáticamente logging para todas las transacciones:

```python
class ERC8004BaseAgent:
    def __init__(self, agent_name: str, private_key: str):
        self.logger = TransactionLogger(private_key, agent_name)

    async def send_payment(self, to_address: str, amount: float, service: str):
        # 1. Sign payment authorization (EIP-3009)
        # 2. Send payment via facilitator
        # 3. Get TX hash
        # 4. LOG THE TRANSACTION ✅
        self.logger.log_payment(
            payment_tx_hash=tx_hash,
            from_agent=self.agent_name,
            to_agent=to_agent_name,
            amount_glue=amount,
            service=service
        )
```

**Resultado:** Cada agente automáticamente loguea todas sus transacciones sin código adicional.

---

## 📚 Archivos Creados

### Contratos
- `erc-20/src/TransactionLogger.sol` - Contrato principal
- `erc-20/script/DeployTransactionLogger.s.sol` - Script de deployment

### Python Helpers
- `shared/transaction_logger.py` - Clase TransactionLogger
- `shared/transaction_logger_example.py` - Ejemplos de uso

### Documentación
- `TRANSACTION_LOGGING.md` - Este archivo

---

## 🔗 Links de Referencia

- **TransactionLogger Contract:** https://testnet.snowtrace.io/address/0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654
- **GLUE Token:** https://testnet.snowtrace.io/address/0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743
- **Karma-Hello Reference:** `z:\ultravioleta\ai\cursor\karma-hello\token_system.py`

---

## ✅ Estado

- ✅ TransactionLogger desplegado y verificado
- ✅ Python helpers implementados
- ✅ Ejemplos de uso creados
- ✅ Documentación completa
- ⏳ Integración en base_agent.py (próximo paso)

**Listo para usar en todos los agentes del ecosistema Karmacadabra!**
