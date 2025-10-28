# 🏔️ Guía de Despliegue en Avalanche Fuji Testnet

Esta guía te muestra cómo desplegar los contratos ERC-8004 en la testnet Fuji de Avalanche.

## 📋 Prerrequisitos

### 1. Foundry (incluye Forge y Cast)
```bash
# Linux/Mac
curl -L https://foundry.paradigm.xyz | bash
foundryup

# Windows
# Descarga desde: https://github.com/foundry-rs/foundry/releases
```

### 2. Wallet con AVAX Testnet

Necesitas una wallet de **PRUEBA** con al menos **0.1 AVAX** en Fuji testnet.

**⚠️ IMPORTANTE:**
- **NUNCA uses una wallet con fondos reales**
- Crea una wallet nueva específicamente para testing
- Guarda la private key de forma segura

#### Obtener AVAX Testnet Gratis:
1. **Faucet Oficial de Avalanche:**
   - https://faucet.avax.network/
   - Conecta tu wallet y solicita tokens

2. **Core App Faucet:**
   - https://core.app/tools/testnet-faucet/
   - Solicita hasta 2 AVAX por día

### 3. Información de la Red Fuji

- **Network Name:** Avalanche Fuji C-Chain
- **RPC URL:** https://avalanche-fuji-c-chain-rpc.publicnode.com
- **Chain ID:** 43113
- **Currency Symbol:** AVAX
- **Block Explorer:** https://testnet.snowtrace.io/

## 🚀 Despliegue Paso a Paso

### Paso 1: Configurar Private Key

Elige **UNA** de estas opciones:

#### Opción A: Variable de Entorno (Temporal)

**Linux/Mac (Bash):**
```bash
export PRIVATE_KEY=0xTU_PRIVATE_KEY_AQUI
```

**Windows (PowerShell):**
```powershell
$env:PRIVATE_KEY = "0xTU_PRIVATE_KEY_AQUI"
```

**Windows (CMD):**
```cmd
set PRIVATE_KEY=0xTU_PRIVATE_KEY_AQUI
```

#### Opción B: Archivo .env.fuji (Recomendado)

1. **Copia el archivo de ejemplo:**
   ```bash
   cp .env.fuji.example .env.fuji
   ```

2. **Edita .env.fuji con tu private key:**
   ```bash
   # Linux/Mac
   nano .env.fuji

   # Windows
   notepad .env.fuji
   ```

3. **Reemplaza la private key:**
   ```
   PRIVATE_KEY=0xTU_PRIVATE_KEY_AQUI
   ```

4. **Carga las variables:**

   **Linux/Mac (Bash):**
   ```bash
   source .env.fuji
   ```

   **PowerShell:**
   ```powershell
   # Renombra o crea .env.fuji.ps1 con:
   # $env:PRIVATE_KEY = "0xTU_PRIVATE_KEY_AQUI"

   . .\.env.fuji.ps1
   ```

### Paso 2: Compilar Contratos

```bash
cd contracts
forge build
cd ..
```

### Paso 3: Ejecutar Script de Despliegue

Elige el script según tu sistema operativo:

#### Linux/Mac (Bash):
```bash
chmod +x deploy-fuji.sh
./deploy-fuji.sh
```

#### Windows (PowerShell):
```powershell
# Permitir ejecución de scripts (solo primera vez)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Ejecutar script
.\deploy-fuji.ps1
```

#### Windows (CMD/Batch):
```cmd
deploy-fuji.bat
```

### Paso 4: Confirmar Despliegue

El script te mostrará:
- ✅ Dirección del deployer
- ✅ Balance actual en AVAX
- ✅ Información de la red

**Ejemplo de salida:**
```
📍 Dirección del deployer: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
💰 Balance: 1.5 AVAX

🚨 CONFIRMACIÓN:
   Network: Avalanche Fuji Testnet
   Chain ID: 43113
   RPC URL: https://avalanche-fuji-c-chain-rpc.publicnode.com

¿Proceder con el despliegue? (y/N):
```

Escribe `y` y presiona Enter para continuar.

### Paso 5: Esperar el Despliegue

El despliegue tomará **1-2 minutos**. Verás:
1. Compilación de contratos
2. Despliegue de IdentityRegistry
3. Despliegue de ReputationRegistry
4. Despliegue de ValidationRegistry

### Paso 6: Obtener Direcciones

Al finalizar, verás las direcciones desplegadas:

```
✅ Contratos desplegados exitosamente en Fuji!

📝 Direcciones desplegadas:
   IdentityRegistry: 0x5FbDB2315678afecb367f032d93F642f64180aa3
   ReputationRegistry: 0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512
   ValidationRegistry: 0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0
```

**Las direcciones también están en:**
```
contracts/broadcast/Deploy.s.sol/43113/run-latest.json
```

## ✅ Verificar el Despliegue

### 1. Ver en Snowtrace

Visita el explorador de bloques de Fuji:
```
https://testnet.snowtrace.io/address/TU_DIRECCION_DE_CONTRATO
```

Reemplaza `TU_DIRECCION_DE_CONTRATO` con una de las direcciones desplegadas.

### 2. Verificar desde la Terminal

**Ver código del contrato:**
```bash
cast code 0xTU_DIRECCION_DE_CONTRATO --rpc-url https://avalanche-fuji-c-chain-rpc.publicnode.com
```

**Leer datos del contrato (ejemplo):**
```bash
# Ver la tarifa de registro del IdentityRegistry
cast call 0xDIRECCION_IDENTITY_REGISTRY "REGISTRATION_FEE()(uint256)" --rpc-url https://avalanche-fuji-c-chain-rpc.publicnode.com
```

## 🔧 Configurar el Demo con Fuji

Una vez desplegados los contratos, actualiza tu configuración local:

### 1. Actualizar deployment.json

```json
{
  "network": "fuji",
  "chainId": 43113,
  "rpcUrl": "https://avalanche-fuji-c-chain-rpc.publicnode.com",
  "contracts": {
    "IdentityRegistry": "0xDIRECCION_DESPLEGADA",
    "ReputationRegistry": "0xDIRECCION_DESPLEGADA",
    "ValidationRegistry": "0xDIRECCION_DESPLEGADA"
  }
}
```

### 2. Actualizar .env

```bash
RPC_URL=https://avalanche-fuji-c-chain-rpc.publicnode.com
CHAIN_ID=43113
PRIVATE_KEY=0xTU_PRIVATE_KEY
```

### 3. Ejecutar el Demo

```bash
python demo.py
```

El demo ahora usará los contratos desplegados en Fuji testnet!

## 🛠️ Despliegue Manual (Alternativa)

Si prefieres desplegar manualmente sin usar el script:

```bash
cd contracts

forge script script/Deploy.s.sol \
  --rpc-url https://avalanche-fuji-c-chain-rpc.publicnode.com \
  --broadcast \
  --private-key $PRIVATE_KEY \
  --legacy \
  -vvv

cd ..
```

**Nota:** El flag `--legacy` usa el formato de transacción EIP-155 (más compatible con algunas RPCs).

## 💰 Costos Estimados

| Operación | Gas Estimado | Costo en AVAX* |
|-----------|--------------|----------------|
| IdentityRegistry | ~800,000 | ~0.02 AVAX |
| ReputationRegistry | ~1,200,000 | ~0.03 AVAX |
| ValidationRegistry | ~1,000,000 | ~0.025 AVAX |
| **TOTAL** | **~3,000,000** | **~0.075 AVAX** |

*Basado en gas price de 25 Gwei. Los costos reales pueden variar.

## ⚠️ Solución de Problemas

### Error: "insufficient funds"

**Solución:** Necesitas más AVAX en tu wallet.
- Visita: https://faucet.avax.network/
- Solicita AVAX testnet gratis

### Error: "nonce too high" o "nonce too low"

**Solución:** Resetea el nonce:
```bash
# Obtén el nonce actual de tu wallet en Fuji
cast nonce 0xTU_DIRECCION --rpc-url https://avalanche-fuji-c-chain-rpc.publicnode.com

# Si es necesario, espera unos segundos y reintentar
```

### Error: "connection refused" o "timeout"

**Solución:**
1. Verifica tu conexión a internet
2. Intenta con otro RPC endpoint:
   ```
   https://api.avax-test.network/ext/bc/C/rpc
   ```

### Error: "invalid private key"

**Solución:**
- Verifica que la private key tenga el prefijo `0x`
- Verifica que tenga exactamente 66 caracteres (0x + 64 hex chars)
- Asegúrate de no incluir espacios

### Los contratos se desplegaron pero no funcionan

**Verificar:**
1. Las direcciones sean correctas en `deployment.json`
2. El CHAIN_ID sea 43113 en `.env`
3. El RPC_URL apunte a Fuji en `.env`

## 🔐 Seguridad

### ⚠️ NUNCA hagas esto:
- ❌ Usar una private key con fondos reales
- ❌ Commitear el archivo `.env.fuji` a Git
- ❌ Compartir tu private key con nadie
- ❌ Usar la misma wallet para testnet y mainnet

### ✅ Mejores prácticas:
- ✅ Usa una wallet dedicada solo para testing
- ✅ Agrega `.env.fuji` a `.gitignore`
- ✅ Guarda backups seguros de tus private keys
- ✅ Usa variables de entorno en producción

## 📚 Recursos Adicionales

- **Documentación de Avalanche:** https://docs.avax.network/
- **Fuji Testnet Info:** https://docs.avax.network/build/dapp/testnet-workflow
- **Foundry Book:** https://book.getfoundry.sh/
- **Snowtrace (Explorer):** https://testnet.snowtrace.io/

## 🎯 Siguiente Paso

Una vez que tus contratos estén en Fuji:
1. ✅ Verifica los contratos en Snowtrace
2. ✅ Actualiza `deployment.json` con las direcciones
3. ✅ Ejecuta `python demo.py` para probar
4. ✅ Comparte las direcciones para que otros interactúen

---

**¿Todo funcionando?** ¡Excelente! Ahora tienes contratos ERC-8004 corriendo en Avalanche Fuji testnet. 🚀
