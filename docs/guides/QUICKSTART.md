# 🚀 Quick Start Guide

> Guía rápida para comenzar con el ecosistema de Trustless Agents en 30 minutos

**Objetivo**: Deploy completo en Fuji testnet y primera transacción entre agentes.

---

## ⏱️ 30-Minute Setup

### Minuto 1-5: Prerequisites

```bash
# 1. Instalar Foundry
curl -L https://foundry.paradigm.xyz | bash
foundryup

# 2. Obtener AVAX testnet
# Visitar: https://faucet.avax.network/
# Solicitar AVAX para tu wallet

# 3. Clonar repo (si aplica)
cd z:\ultravioleta\dao\karmacadabra
```

---

### Minuto 6-10: Deploy UVD Token

```bash
cd erc-20

# Setup
cp .env.example .env
# Editar .env con tu PRIVATE_KEY

# Deploy
forge build
./deploy-fuji.sh

# Guardar address
# UVD Token: 0x...
```

---

### Minuto 11-15: Deploy ERC-8004 Contracts

```bash
cd ../erc-8004

# Setup
cp .env.fuji.example .env.fuji
source .env.fuji

# Deploy
cd contracts && forge build && cd ..
./deploy-fuji.sh

# Guardar addresses
# IdentityRegistry: 0x...
# ReputationRegistry: 0x...
# ValidationRegistry: 0x...
```

---

### Minuto 16-20: Setup x402 Facilitator

```bash
cd ../x402-rs

# Configure
cat > .env << EOF
SIGNER_TYPE=private-key
EVM_PRIVATE_KEY=0x...
RPC_URL_FUJI=https://avalanche-fuji-c-chain-rpc.publicnode.com
HOST=0.0.0.0
PORT=8080
EOF

# Build & Run
cargo build --release
cargo run &

# Test
curl http://localhost:8080/health
```

---

### Minuto 21-25: Setup Agents

```bash
# Validator
cd ../validator
cp .env.example .env
# Editar .env
pip install -r requirements.txt
python scripts/register_validator.py
python main.py &

# Karma-Hello Seller
cd ../karma-hello-agent
cp .env.example .env
# Editar .env
pip install -r requirements.txt
python scripts/register_seller.py
python main.py --mode seller &

# Abracadabra Seller
cd ../abracadabra-agent
cp .env.example .env
# Editar .env
pip install -r requirements.txt
python scripts/register_seller.py
python main.py --mode seller &
```

---

### Minuto 26-30: Primera Transacción

```bash
# Demo completo
cd ..
python demo.py

# Output esperado:
# ✅ All agents registered
# ✅ KarmaHello bought transcript: 0.02 UVD
# ✅ Validation score: 95/100
# ✅ Transaction verified on-chain
# 🎉 Demo completed!
```

---

## 🎯 Verificación

### 1. Contratos en Snowtrace

```
https://testnet.snowtrace.io/address/0xYOUR_UVD_ADDRESS
https://testnet.snowtrace.io/address/0xYOUR_IDENTITY_REGISTRY
```

### 2. Agentes Registrados

```bash
cast call $IDENTITY_REGISTRY \
  "getAgent(uint256)(uint256,string,address)" \
  1 \
  --rpc-url https://avalanche-fuji-c-chain-rpc.publicnode.com

# Output: (1, "karma-hello-seller.ultravioletadao.xyz", 0x...)
```

### 3. Balance UVD

```bash
cast call $UVD_TOKEN \
  "balanceOf(address)(uint256)" \
  $YOUR_WALLET \
  --rpc-url https://avalanche-fuji-c-chain-rpc.publicnode.com

# Output: 100000000000 (100k UVD)
```

---

## 🐛 Troubleshooting

### Error: "insufficient funds"
→ Obtener más AVAX: https://faucet.avax.network/

### Error: "nonce too high"
→ Esperar 10 segundos y reintentar

### Error: "agent not registered"
→ Correr `python scripts/register_*.py`

### Error: "facilitator connection refused"
→ Verificar que x402-rs esté corriendo: `curl http://localhost:8080/health`

---

## 📚 Siguiente Paso

Una vez que todo funciona:

1. **Leer [MASTER_PLAN.md](../../MASTER_PLAN.md)** para entender el sistema completo
2. **Explorar [ARCHITECTURE.md](../ARCHITECTURE.md)** para detalles técnicos
3. **Revisar READMEs** de cada componente para customización

---

## 🎉 ¡Listo!

Ya tienes un ecosistema completo de trustless agents funcionando en Fuji testnet.

**Próximos pasos**:
- Modificar precios en agentes
- Agregar nuevos skills en AgentCards
- Implementar lógica de auto-compra personalizada
- Testing exhaustivo antes de mainnet

---

**¿Problemas?** Consultar [MASTER_PLAN.md](./MASTER_PLAN.md) sección "Solución de Problemas"
