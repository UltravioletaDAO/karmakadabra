# 🎯 Karmacadabra: Economía de Agentes Sin Confianza

> Agentes AI que compran/venden datos autónomamente usando micropagos blockchain sin gas

**🇪🇸 Versión en Español** | **[🇺🇸 English Version](./README.md)**

[![Avalanche](https://img.shields.io/badge/Avalanche-Fuji-E84142?logo=avalanche)](https://testnet.snowtrace.io/)
[![ERC-8004](https://img.shields.io/badge/ERC--8004%20Extended-Reputación%20Bidireccional-blue)](https://eips.ethereum.org/EIPS/eip-8004)
[![x402](https://img.shields.io/badge/x402-Protocolo%20de%20Pago-green)](https://www.x402.org)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)

---

## 📦 Qué Está Implementado

### ✅ Fase 1: Infraestructura Blockchain (COMPLETA)

**Desplegado en Avalanche Fuji Testnet** - 22 de Octubre, 2025

| Contrato | Dirección | Chain ID |
|----------|-----------|----------|
| **GLUE Token (EIP-3009)** | [\`0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743\`](https://testnet.snowtrace.io/address/0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743) | 43113 |
| **Identity Registry** | [\`0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618\`](https://testnet.snowtrace.io/address/0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618) | 43113 |
| **Reputation Registry** | [\`0x932d32194C7A47c0fe246C1d61caF244A4804C6a\`](https://testnet.snowtrace.io/address/0x932d32194C7A47c0fe246C1d61caF244A4804C6a) | 43113 |
| **Validation Registry** | [\`0x9aF4590035C109859B4163fd8f2224b820d11bc2\`](https://testnet.snowtrace.io/address/0x9aF4590035C109859B4163fd8f2224b820d11bc2) | 43113 |
| **Transaction Logger** | [\`0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654\`](https://testnet.snowtrace.io/address/0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654) | 43113 |

**Wallets de Agentes** (Fondeadas con 55,000 GLUE cada una):
- Validator: \`0x1219eF9484BF7E40E6479141B32634623d37d507\`
- Karma-Hello: \`0x2C3e071df446B25B821F59425152838ae4931E75\`
- Abracadabra: \`0x940DDDf6fB28E611b132FbBedbc4854CC7C22648\`
- Client Agent: \`0xCf30021812F27132d36dc791E0eC17f34B4eE8BA\`

### ✅ Sprint 1: Fundamentos (COMPLETO - Octubre 2025)

**Utilidades Compartidas en Python** (\`shared/\`) - 3,100+ líneas de código productivo:

1. **\`base_agent.py\`** (600+ líneas) - Integración ERC-8004, reputación, Web3.py, AWS Secrets
2. **\`payment_signer.py\`** (470+ líneas) - Firma EIP-712, firmas EIP-3009
3. **\`x402_client.py\`** (530+ líneas) - Protocolo de pago HTTP x402
4. **\`a2a_protocol.py\`** (650+ líneas) - Descubrimiento de agentes, AgentCard, Skills
5. **\`validation_crew.py\`** (550+ líneas) - Patrón de validación CrewAI
6. **\`tests/\`** (1,200+ líneas) - 26 tests unitarios pasando + framework de integración

**Documentación API**: [\`shared/README.md\`](./shared/README.md)

### 🔴 Fase 2: Desarrollo de Agentes (SIGUIENTE)

Fundamentos completos, ahora implementando agentes:
- Validator - Verificación de calidad de datos
- Karma-Hello - Logs de chat de Twitch
- Abracadabra - Transcripciones de streams
- Client - Comprador genérico

---

## 🏗️ Arquitectura

\`\`\`
┌────────────────────────────────────────┐
│ Avalanche Fuji (Capa 1)               │
│ • GLUE Token (EIP-3009)                │
│ • Registros ERC-8004                   │
└────────────┬───────────────────────────┘
             │ Web3.py
┌────────────┴───────────────────────────┐
│ Facilitador x402 (Capa 2 - Rust)      │
│ • Verifica firmas EIP-712              │
│ • Ejecuta transferencias on-chain      │
└────────────┬───────────────────────────┘
             │ httpx
┌────────────┴───────────────────────────┐
│ Agentes AI (Capa 3 - Python)          │
│ • Descubrimiento A2A • Validación      │
└────────────────────────────────────────┘
\`\`\`

**Innovación Clave**: Los agentes no necesitan gas - firman pagos off-chain (EIP-712), el facilitador ejecuta on-chain.

---

## 🚀 Inicio Rápido

\`\`\`bash
git clone https://github.com/ultravioletadao/karmacadabra.git
cd karmacadabra/shared
pip install web3 boto3 eth-account python-dotenv httpx pydantic crewai
cd tests && pytest -m unit  # 26 tests pasando
\`\`\`

**Ejemplo de Uso:**

\`\`\`python
from shared import ERC8004BaseAgent, sign_payment, X402Client

# Registrar agente
agent = ERC8004BaseAgent(
    agent_name="mi-agente",
    agent_domain="mi-agente.ultravioletadao.xyz"
)
agent_id = agent.register_agent()

# Firmar pago
sig = sign_payment(
    from_address="0xComprador...",
    to_address="0xVendedor...",
    amount_glue="0.01",
    private_key="0x..."
)

# Comprar datos
async with X402Client(private_key="0x...") as client:
    response, settlement = await client.buy_with_payment(
        seller_url="https://vendedor.xyz/api/data",
        seller_address="0xVendedor...",
        amount_glue="0.01"
    )
\`\`\`

---

## 📚 Documentación

- **[MASTER_PLAN.md](./MASTER_PLAN.md)** - Hoja de ruta y arquitectura
- **[shared/README.md](./shared/README.md)** - Referencia API
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Decisiones técnicas
- **[shared/tests/README.md](./shared/tests/README.md)** - Guía de testing

---

## 🧪 Testing

\`\`\`bash
cd shared/tests
pytest -m unit              # 26 tests pasando (rápido)
pytest -m integration       # Integración con Fuji testnet
pytest --cov=shared         # Con cobertura
\`\`\`

---

## 🏔️ ¿Por Qué Avalanche?

- **Hogar de Ultravioleta DAO** - Donde nació nuestra DAO
- **Finalidad de 2 segundos** - Transacciones instantáneas
- **Fees bajos** - Micropagos de 0.01 GLUE viables
- **Compatible EVM** - Soporte completo de Solidity

**ERC-8004 Extended**: Reputación bidireccional personalizada (compradores + vendedores se califican)

---

## 💡 Tecnologías

| Tech | Estado |
|------|--------|
| Solidity + Foundry | ✅ Desplegado |
| Rust (x402) | ⚠️ Externo |
| Python 3.11 | ✅ Fundamentos listos |
| Web3.py | ✅ Integrado |
| CrewAI | ✅ Patrón implementado |
| pytest | ✅ 26 tests pasando |

---

## 🔧 Herramientas

\`\`\`bash
# Generar wallet
python generate-wallet.py --name mi-agente

# Distribuir GLUE
cd erc-20 && python distribute-token.py

# Verificar agente
python -c "from shared import ERC8004BaseAgent; ..."
\`\`\`

---

## 🚧 Hoja de Ruta

- ✅ Fase 1: Contratos desplegados
- ✅ Sprint 1: Fundamentos completos
- 🔴 Sprint 2: Agentes (en progreso)
- 📋 Fase 3: Datos de producción
- 📋 Fase 4: Mainnet

**Hoja de ruta completa**: [MASTER_PLAN.md](./MASTER_PLAN.md)

---

## 🔗 Enlaces

- [Snowtrace Explorer](https://testnet.snowtrace.io/)
- [GLUE Token](https://testnet.snowtrace.io/address/0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743)
- [Fuji Faucet](https://faucet.avax.network/)
- [Spec ERC-8004](https://eips.ethereum.org/EIPS/eip-8004)
- [Protocolo x402](https://www.x402.org)

---

**Construido con ❤️ por Ultravioleta DAO en Avalanche**
