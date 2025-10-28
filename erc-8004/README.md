# 🔐 ERC-8004 Registries - Trust Frameworks for AI Agents

> Contratos de identidad, reputación y validación on-chain para agentes AI autónomos

**Versión**: 1.0.0
**Network**: Avalanche Fuji Testnet (Chain ID: 43113)
**Estado**: ✅ Listo para desplegar
**Última actualización**: Octubre 21, 2025

---

## 🗂️ Ubicación en el Proyecto

```
z:\ultravioleta\dao\karmacadabra\
├── erc-20/                    (GLUE Token)
├── erc-8004/                  ← ESTÁS AQUÍ
├── x402-rs/                   (x402 Facilitator)
├── validator/                 (Validator Agent - USA estos contratos)
├── karma-hello-agent/         (Sellers/Buyers - SE REGISTRAN aquí)
├── abracadabra-agent/         (Sellers/Buyers - SE REGISTRAN aquí)
├── MASTER_PLAN.md            (Plan completo del proyecto)
└── MONETIZATION_OPPORTUNITIES.md
```

**Parte del Master Plan**: Phase 1 - Blockchain Infrastructure (Semana 1-2)

---

## 🎯 Descripción

Este directorio contiene todo lo necesario para desplegar los contratos **ERC-8004** en Avalanche Fuji Testnet.

### ¿Qué es ERC-8004?

**ERC-8004** es un estándar para crear **frameworks de confianza** para agentes AI. Proporciona 3 registros on-chain:

1. **IdentityRegistry**: Registro de agentes con dominios verificables
2. **ReputationRegistry**: Sistema de feedback y ratings bidireccionales
3. **ValidationRegistry**: Registro de validaciones y scores de calidad

### Rol en el Ecosistema

**Todos los agentes** del ecosistema se registran aquí:

**Agentes que se registran**:
- ✅ **Karma-Hello Seller** (Agent ID: 1) → vende logs de Twitch
- ✅ **Abracadabra Seller** (Agent ID: 2) → vende transcripciones
- ✅ **Validator Agent** (Agent ID: 3) → valida transacciones
- ✅ **Karma-Hello Buyer** (Agent ID: 4) → compra transcripciones
- ✅ **Abracadabra Buyer** (Agent ID: 5) → compra logs

**Datos on-chain**:
- Identidad verificable con dominio (ej: `karma-hello-seller.ultravioletadao.xyz`)
- Reputación acumulada de transacciones
- Historial de validaciones (para validator)
- Ratings de clientes y proveedores

**Caso de uso en flujo de pago**:
1. KarmaHello Buyer quiere comprar transcript (0.02 UVD)
2. Solicita validación → ValidationRegistry registra request
3. Validator valida y sube score (0-100) → queda on-chain
4. Si score > 80, pago procede
5. Después del pago, ambos agentes se dan rating → ReputationRegistry actualiza

## Inicio Rápido

### 1. Instalar Foundry

Si no tienes Foundry instalado:

**Windows:**
- Descarga desde: https://github.com/foundry-rs/foundry/releases

**Linux/Mac:**
```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

### 2. Obtener AVAX Testnet

Necesitas al menos 0.1 AVAX en Fuji testnet:
- **Faucet Oficial:** https://faucet.avax.network/
- **Core App Faucet:** https://core.app/tools/testnet-faucet/

### 3. Configurar Private Key

**Opción A - Variable de Entorno:**

**PowerShell:**
```powershell
$env:PRIVATE_KEY = "0xTU_PRIVATE_KEY_AQUI"
```

**CMD:**
```cmd
set PRIVATE_KEY=0xTU_PRIVATE_KEY_AQUI
```

**Bash:**
```bash
export PRIVATE_KEY=0xTU_PRIVATE_KEY_AQUI
```

**Opción B - Archivo .env.fuji (Recomendado):**
```bash
cp .env.fuji.example .env.fuji
# Edita .env.fuji con tu private key
```

### 4. Compilar Contratos

```bash
cd contracts
forge build
cd ..
```

### 5. Desplegar

**PowerShell:**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\deploy-fuji.ps1
```

**CMD/Batch:**
```cmd
deploy-fuji.bat
```

**Bash:**
```bash
chmod +x deploy-fuji.sh
./deploy-fuji.sh
```

## Archivos Incluidos

```
erc-8004/
├── contracts/
│   ├── src/
│   │   ├── IdentityRegistry.sol       # Registro de agentes
│   │   ├── ReputationRegistry.sol     # Sistema de reputación
│   │   └── ValidationRegistry.sol     # Validaciones
│   ├── script/
│   │   └── Deploy.s.sol               # Script de deploy
│   ├── test/
│   └── foundry.toml
├── deploy-fuji.sh                     # Deploy para Linux/Mac
├── deploy-fuji.ps1                    # Deploy para PowerShell
├── deploy-fuji.bat                    # Deploy para Windows CMD
├── .env.fuji.example                  # Configuración
├── DEPLOY-FUJI.md                     # Guía completa
└── README.md                          # ← Este archivo
```

## Información de la Red

- **Network:** Avalanche Fuji C-Chain
- **RPC URL:** https://avalanche-fuji-c-chain-rpc.publicnode.com
- **Chain ID:** 43113
- **Explorer:** https://testnet.snowtrace.io/

## Costos Estimados

El despliegue completo cuesta aproximadamente **0.075 AVAX** (~$2 USD).

## 📊 Contratos Desplegados

Después del deploy, los addresses quedarán en `deployment.json`:

```json
{
  "network": "fuji",
  "chainId": 43113,
  "contracts": {
    "IdentityRegistry": "0x...",
    "ReputationRegistry": "0x...",
    "ValidationRegistry": "0x..."
  }
}
```

**Los agentes necesitan estos addresses para**:
- Registrarse con `IdentityRegistry.newAgent(domain, address)`
- Dar feedback con `ReputationRegistry.acceptFeedback(from, to)`
- Solicitar validaciones con `ValidationRegistry.validationRequest(...)`

Ver `MASTER_PLAN.md` § "ERC-8004: Trust Frameworks for AI Agents" para detalles de uso.

---

## 🔗 Referencias

- **ERC-8004 Spec**: https://eips.ethereum.org/EIPS/eip-8004
- **Ejemplo Original**: `z:\erc8004\erc-8004-example`
- **Trustless Agents Course**: https://intensivecolearn.ing/en/programs/trustless-agents
- **Snowtrace Explorer**: https://testnet.snowtrace.io/

---

## Seguridad

- Usa SIEMPRE una wallet de prueba
- NUNCA uses private keys con fondos reales
- Agrega `.env.fuji` a `.gitignore`

## Documentación Completa

Para instrucciones detalladas, solución de problemas y mejores prácticas, consulta:
- **[DEPLOY-FUJI.md](./DEPLOY-FUJI.md)** - Guía completa paso a paso

## Verificar Despliegue

Una vez desplegados, las direcciones estarán en:
```
contracts/broadcast/Deploy.s.sol/43113/run-latest.json
```

Puedes verificar en el explorador:
```
https://testnet.snowtrace.io/address/TU_DIRECCION_DE_CONTRATO
```

## Soporte

- **Documentación Avalanche:** https://docs.avax.network/
- **Foundry Book:** https://book.getfoundry.sh/
