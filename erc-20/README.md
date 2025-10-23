# 🪙 GLUE Token - ERC-20 con EIP-3009

> Token ERC-20 con soporte de meta-transacciones gasless para el ecosistema Ultravioleta DAO

**Versión**: 1.0.0
**Network**: Avalanche Fuji Testnet (Chain ID: 43113)
**Estado**: ✅ Desplegado y Verificado
**Dirección**: `0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743`
**Última actualización**: Octubre 23, 2025

---

## 🗂️ Ubicación en el Proyecto

```
z:\ultravioleta\dao\karmacadabra\
├── erc-20/                    ← ESTÁS AQUÍ
├── erc-8004/                  (ERC-8004 Registries)
├── x402-rs/                   (x402 Facilitator)
├── validator/                 (Validator Agent)
├── karma-hello-agent/         (Karma-Hello Sellers/Buyers)
├── abracadabra-agent/         (Abracadabra Sellers/Buyers)
├── MASTER_PLAN.md            (Plan completo del proyecto)
└── MONETIZATION_OPPORTUNITIES.md
```

**Parte del Master Plan**: Phase 1 - Blockchain Infrastructure (Semana 1-2)

---

## 📋 Tabla de Contenidos

1. [Descripción](#-descripción)
2. [Características](#-características)
3. [Instalación](#-instalación)
4. [Despliegue](#-despliegue)
5. [Uso](#-uso)
6. [Integración con x402](#-integración-con-x402)
7. [Testing](#-testing)
8. [Seguridad](#-seguridad)

---

## 🎯 Descripción

**GLUE Token** (Gasless Lightweight Ultraviolet Economy) es el token nativo del ecosistema de agentes autónomos de Ultravioleta DAO. Su característica principal es el soporte de **transferencias gasless** mediante EIP-3009, permitiendo que agentes AI realicen micropagos sin necesitar ETH/AVAX para gas.

### Rol en el Ecosistema

GLUE es la **moneda de pago** para todos los servicios comercializados entre agentes:

- **Karma-Hello Agent** vende logs de streams: 0.01-1.00 GLUE por servicio
- **Abracadabra Agent** vende transcripciones: 0.02-3.00 GLUE por servicio
- **Validator Agent** cobra fees de validación: 0.001 GLUE por validación
- **Cross-Platform Bundles**: 0.25-1.80 GLUE con descuentos

**Total de servicios monetizables**: 50+ productos (ver `MONETIZATION_OPPORTUNITIES.md`)

**Revenue proyectado**:
- Scenario conservador: 1,800 GLUE/año (100 agentes)
- Scenario moderado: 120,000 GLUE/año (1,000 agentes)
- Scenario optimista: 3,000,000 GLUE/año (10,000 agentes)

### ¿Por qué EIP-3009?

Los agentes AI necesitan:
- ✅ **No mantener AVAX** para gas fees
- ✅ **Transacciones instantáneas** sin esperar confirmaciones de aprobación
- ✅ **Micropagos eficientes** (<$0.01 USD)
- ✅ **Operación autónoma** sin intervención humana

EIP-3009 `transferWithAuthorization` permite esto mediante **meta-transacciones**: el usuario firma off-chain, y un relayer (facilitator) ejecuta la transacción on-chain pagando el gas.

---

## ✨ Características

### ERC-20 Estándar
- `transfer(to, amount)`
- `approve(spender, amount)`
- `transferFrom(from, to, amount)`
- `balanceOf(account)`
- `totalSupply()`

### EIP-3009: Transfer With Authorization
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

**Ventajas**:
- Usuario firma EIP-712 message off-chain
- Cualquiera puede enviar la firma on-chain (relayer paga gas)
- Atómico y seguro (nonce para evitar replay attacks)

### EIP-2612: Permit (Approvals Gasless)
```solidity
function permit(
    address owner,
    address spender,
    uint256 value,
    uint256 deadline,
    uint8 v,
    bytes32 r,
    bytes32 s
) external;
```

**Uso**: Approvals sin gas (útil para DEXs, contratos)

### Token Parameters
- **Name**: GLUE Token
- **Symbol**: GLUE
- **Decimals**: 6 (matching USDC for lower gas costs)
- **Initial Supply**: 24,157,817 GLUE
- **Owner Wallet**: 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8
- **Total Supply**: 24,157,817,000,000 (with decimals)
- **Deployed Address**: 0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743

### Security Features
- ✅ **Nonce-based Replay Protection**: Each authorization can only be used once
- ✅ **Time-window Validation**: validAfter/validBefore timestamps
- ✅ **EIP-712 Signature Verification**: Type-safe signed messages
- ✅ **Cancel Authorization**: Users can revoke unused authorizations
- ✅ **Ownable**: Admin control for owner wallet

---

## 🚀 Instalación

### Requisitos Previos

- **Foundry** (forge, cast, anvil)
- **Wallet con AVAX** en Fuji testnet
- **Git**

### Instalación de Foundry

```bash
# Linux/Mac
curl -L https://foundry.paradigm.xyz | bash
foundryup

# Windows
# Descargar desde: https://github.com/foundry-rs/foundry/releases
```

### Obtener AVAX Testnet

```bash
# Faucets oficiales:
# 1. https://faucet.avax.network/
# 2. https://core.app/tools/testnet-faucet/
```

### Clonar e Instalar

```bash
cd z:\ultravioleta\dao\karmacadabra\erc-20

# Instalar dependencias (OpenZeppelin)
forge install OpenZeppelin/openzeppelin-contracts
```

---

## 📦 Despliegue

### Prerequisites

```bash
# 1. Install Foundry
curl -L https://foundry.paradigm.xyz | bash
foundryup

# 2. Get testnet AVAX (~0.5 AVAX for deployment gas)
# https://faucet.avax.network/

# 3. Have deployer wallet private key ready
```

### Configuración

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit .env with your values
nano .env

# Required:
# - PRIVATE_KEY: Your deployer wallet private key
# - RPC_URL_AVALANCHE_FUJI: Your custom RPC (or use public fallback)

# Optional:
# - SNOWTRACE_API_KEY: For contract verification
```

### Install Dependencies

```bash
# Install OpenZeppelin contracts
forge install OpenZeppelin/openzeppelin-contracts --no-commit

# Install Forge Standard Library
forge install foundry-rs/forge-std --no-commit
```

### Deploy to Fuji Testnet

**Automated Deployment (Recommended):**

```bash
# Make script executable
chmod +x deploy-fuji.sh

# Run deployment
./deploy-fuji.sh
```

**The script will:**
1. ✅ Build contracts with `forge build`
2. ✅ Deploy GLUE contract to Avalanche Fuji
3. ✅ Mint 24,157,817 GLUE to owner wallet
4. ✅ Verify contract on Snowtrace (if API key provided)
5. ✅ Save deployment info to `deployment.json`
6. ✅ Display next steps for x402 configuration

**Expected Output:**

```
========================================
GLUE Token Deployment
========================================
Network: Avalanche Fuji Testnet
Chain ID: 43113

Contract Address: 0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743
Token Name: GLUE Token
Token Symbol: GLUE
Decimals: 6
Initial Supply: 24,157,817 GLUE
Total Supply (with decimals): 24,157,817,000,000
Owner: 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8
Owner Balance: 24,157,817 GLUE
========================================

Deployment info saved to: deployment.json
```

### Manual Deployment (Advanced)

```bash
# 1. Build contracts
forge build

# 2. Deploy using forge script
forge script script/DeployGLUE.s.sol:DeployGLUE \
  --rpc-url $RPC_URL_AVALANCHE_FUJI \
  --broadcast \
  --verify \
  -vvvv
```

### Verify on Snowtrace

If auto-verification failed:

```bash
# Get deployed address from deployment.json
TOKEN_ADDRESS=$(cat deployment.json | jq -r '.tokenAddress')

# Verify manually
forge verify-contract \
  $TOKEN_ADDRESS \
  src/GLUE.sol:GLUE \
  --chain-id 43113 \
  --verifier blockscout \
  --verifier-url https://api.routescan.io/v2/network/testnet/evm/43113/etherscan
```

### Post-Deployment

```bash
# 1. Verify deployment.json was created
cat deployment.json

# Expected output:
# {
#   "network": "avalanche-fuji",
#   "chainId": 43113,
#   "tokenAddress": "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743",
#   "tokenName": "GLUE Token",
#   "tokenSymbol": "GLUE",
#   "decimals": 6,
#   "initialSupply": 24157817,
#   "owner": "0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8",
#   "deployedAt": 1761242932
# }

# 2. Update x402 facilitator configuration
TOKEN_ADDRESS=$(cat deployment.json | jq -r '.tokenAddress')
echo "GLUE_TOKEN_ADDRESS=$TOKEN_ADDRESS" >> ../x402-rs/.env

# 3. Verify on Snowtrace
echo "https://testnet.snowtrace.io/address/$TOKEN_ADDRESS"

# 4. Check owner balance
cast call $TOKEN_ADDRESS "balanceOf(address)(uint256)" 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8 \
  --rpc-url $RPC_URL_AVALANCHE_FUJI

# Expected: 24157817000000 (24,157,817 GLUE with 6 decimals)
```

---

## 💡 Uso

### Transferencias Normales (con gas)

```javascript
// JavaScript/TypeScript (ethers.js)
const token = new ethers.Contract(GLUE_ADDRESS, GLUE_ABI, signer);

// Transfer
await token.transfer(recipientAddress, ethers.parseUnits("10", 6));

// Approve
await token.approve(spenderAddress, ethers.parseUnits("100", 6));
```

### Transferencias Gasless (EIP-3009)

```javascript
import { ethers } from 'ethers';

// 1. Preparar autorización
const from = await signer.getAddress();
const to = "0x..."; // Recipient
const value = ethers.parseUnits("0.02", 6); // 0.02 GLUE
const validAfter = 0;
const validBefore = Math.floor(Date.now() / 1000) + 3600; // 1 hora
const nonce = ethers.hexlify(ethers.randomBytes(32));

// 2. Domain separator (EIP-712)
const domain = {
  name: "GLUE Token",
  version: "1",
  chainId: 43113,
  verifyingContract: GLUE_ADDRESS
};

// 3. Types
const types = {
  TransferWithAuthorization: [
    { name: "from", type: "address" },
    { name: "to", type: "address" },
    { name: "value", type: "uint256" },
    { name: "validAfter", type: "uint256" },
    { name: "validBefore", type: "uint256" },
    { name: "nonce", type: "bytes32" }
  ]
};

// 4. Firmar
const signature = await signer.signTypedData(domain, types, {
  from,
  to,
  value,
  validAfter,
  validBefore,
  nonce
});

const { v, r, s } = ethers.Signature.from(signature);

// 5. Enviar a facilitator o ejecutar directamente
const tx = await token.transferWithAuthorization(
  from, to, value, validAfter, validBefore, nonce, v, r, s
);

await tx.wait();
console.log("Transfer gasless completado!");
```

### Python (web3.py)

```python
from web3 import Web3
from eth_account.messages import encode_typed_data
import secrets

w3 = Web3(Web3.HTTPProvider("https://avalanche-fuji-c-chain-rpc.publicnode.com"))

# 1. Preparar datos
from_address = "0x..."
to_address = "0x..."
value = 20000  # 0.02 GLUE (6 decimals)
valid_after = 0
valid_before = int(time.time()) + 3600
nonce = "0x" + secrets.token_hex(32)

# 2. EIP-712 domain
domain = {
    "name": "GLUE Token",
    "version": "1",
    "chainId": 43113,
    "verifyingContract": GLUE_ADDRESS
}

# 3. Message
message = {
    "from": from_address,
    "to": to_address,
    "value": value,
    "validAfter": valid_after,
    "validBefore": valid_before,
    "nonce": nonce
}

# 4. Types
types = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"}
    ],
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"}
    ]
}

# 5. Firmar
structured_msg = encode_typed_data(
    domain_data=domain,
    message_types=types,
    message_data=message
)

signed = w3.eth.account.sign_message(structured_msg, private_key=PRIVATE_KEY)

# 6. Ejecutar
token = w3.eth.contract(address=GLUE_ADDRESS, abi=GLUE_ABI)
tx = token.functions.transferWithAuthorization(
    from_address,
    to_address,
    value,
    valid_after,
    valid_before,
    bytes.fromhex(nonce[2:]),
    signed.v,
    signed.r,
    signed.s
).transact({'from': RELAYER_ADDRESS})  # Relayer paga gas

receipt = w3.eth.wait_for_transaction_receipt(tx)
print(f"Transfer gasless completado: {receipt.transactionHash.hex()}")
```

---

## 🔌 Integración con x402

El token GLUE está diseñado para funcionar perfectamente con el protocolo x402 para micropagos HTTP.

### Configuración en x402-rs

```rust
// x402-rs/src/network.rs

use crate::types::{TokenAsset, TokenDeployment, TokenAssetEip712};
use crate::network::Network;

pub struct GLUEDeployment;

impl GLUEDeployment {
    pub fn by_network(network: Network) -> TokenDeployment {
        match network {
            Network::AvalancheFuji => TokenDeployment {
                asset: TokenAsset {
                    address: "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743".parse().unwrap(),
                    network: Network::AvalancheFuji,
                },
                decimals: 6,
                eip712: TokenAssetEip712 {
                    name: "GLUE Token".into(),
                    version: "1".into(),
                },
            },
            _ => panic!("GLUE not deployed on {:?}", network)
        }
    }
}
```

### Uso en Agentes

```python
# karma-hello-agent/agents/karma_hello_seller.py

from x402_axum import X402Middleware, IntoPriceTag
from network import GLUEDeployment, Network

# Setup x402 middleware
x402 = X402Middleware(facilitator_url="https://facilitator.ultravioletadao.xyz")
glue = GLUEDeployment.by_network(Network.AvalancheFuji)

# Define precio
price_tag = glue.amount("0.01").pay_to(SELLER_WALLET_ADDRESS)

# Aplicar a endpoint
@app.post("/api/logs")
@x402.require_payment(price_tag)
async def get_logs(request: LogsRequest):
    # Este endpoint solo se ejecuta si el pago es válido
    logs = fetch_logs_from_db(request.stream_id)
    return {"logs": logs}
```

---

## 🧪 Testing

### Tests Locales con Anvil

```bash
# Terminal 1: Iniciar Anvil
anvil --chain-id 43113

# Terminal 2: Deploy y test
forge test -vv

# Run tests específicos
forge test --match-contract UVDTokenTest
forge test --match-test testTransferWithAuthorization
```

### Tests de Integración

```bash
# Test con Fuji testnet
forge test --fork-url https://avalanche-fuji-c-chain-rpc.publicnode.com -vv
```

### Test de EIP-3009 Gasless

```solidity
// test/GLUEToken.t.sol

function testTransferWithAuthorizationGasless() public {
    // Setup
    address alice = makeAddr("alice");
    address bob = makeAddr("bob");
    uint256 amount = 100 * 10**6; // 100 GLUE

    // Mint to Alice
    token.mint(alice, amount);

    // Alice firma autorización
    uint256 aliceKey = 0x1234...;
    bytes32 nonce = keccak256("unique-nonce-1");
    uint256 validAfter = 0;
    uint256 validBefore = block.timestamp + 3600;

    bytes32 structHash = keccak256(abi.encode(
        TRANSFER_WITH_AUTHORIZATION_TYPEHASH,
        alice,
        bob,
        amount,
        validAfter,
        validBefore,
        nonce
    ));

    bytes32 digest = keccak256(abi.encodePacked(
        "\x19\x01",
        DOMAIN_SEPARATOR,
        structHash
    ));

    (uint8 v, bytes32 r, bytes32 s) = vm.sign(aliceKey, digest);

    // Relayer (cualquiera) ejecuta
    vm.prank(address(this)); // Relayer paga gas
    token.transferWithAuthorization(
        alice, bob, amount, validAfter, validBefore, nonce, v, r, s
    );

    // Verificar
    assertEq(token.balanceOf(bob), amount);
    assertEq(token.balanceOf(alice), 0);
}
```

---

## 🔐 Seguridad

### Auditoría

⚠️ **Este contrato NO ha sido auditado**. Usar solo en testnet.

Para mainnet:
- [ ] Auditoría por firma reconocida (OpenZeppelin, Trail of Bits, etc.)
- [ ] Bug bounty program
- [ ] Timelock para funciones admin
- [ ] Multi-sig para owner

### Mejores Prácticas

1. **Nonces Únicos**: Siempre usar nonces aleatorios para `transferWithAuthorization`
2. **Validez Temporal**: Usar `validBefore` razonable (max 1 hora)
3. **Verificar Firmas**: Nunca confiar en firmas sin verificar
4. **Rate Limiting**: Implementar en facilitator para prevenir spam

### Riesgos Conocidos

- **Replay Attacks**: Mitigado con nonces únicos
- **Phishing**: Usuarios deben verificar `to` y `value` antes de firmar
- **Facilitator Down**: Si el facilitator cae, se puede ejecutar directamente on-chain

---

## 📚 Referencias

- **EIP-3009**: https://eips.ethereum.org/EIPS/eip-3009
- **EIP-712**: https://eips.ethereum.org/EIPS/eip-712
- **EIP-2612**: https://eips.ethereum.org/EIPS/eip-2612
- **OpenZeppelin**: https://docs.openzeppelin.com/contracts/
- **Foundry Book**: https://book.getfoundry.sh/

---

## 📝 Licencia

MIT License - Ver LICENSE para detalles

---

**Desarrollado con ❤️ por Ultravioleta DAO**
