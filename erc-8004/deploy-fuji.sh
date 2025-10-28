#!/bin/bash

# Script para desplegar los contratos ERC-8004 en Avalanche Fuji Testnet

set -e

echo "🏔️  Desplegando contratos ERC-8004 en Avalanche Fuji Testnet..."
echo ""

# Configuración de Fuji
FUJI_RPC_URL="https://avalanche-fuji-c-chain-rpc.publicnode.com"
FUJI_CHAIN_ID=43113

# Verificar que se proporcione la private key
if [ -z "$PRIVATE_KEY" ]; then
  echo "⚠️  La variable de entorno PRIVATE_KEY no está configurada."
  echo ""
  echo "Por favor, exporta tu private key:"
  echo "  export PRIVATE_KEY=0x..."
  echo ""
  echo "O créala en un archivo .env.fuji:"
  echo "  PRIVATE_KEY=0x..."
  echo "  Y luego ejecuta: source .env.fuji"
  echo ""
  exit 1
fi

# Advertencia de seguridad
echo "⚠️  ADVERTENCIA DE SEGURIDAD:"
echo "   - Asegúrate de usar una wallet de PRUEBA"
echo "   - NUNCA uses una private key con fondos reales"
echo "   - Esta transacción se ejecutará en Fuji TESTNET"
echo ""

# Derivar la dirección de la private key
DEPLOYER_ADDRESS=$(cast wallet address $PRIVATE_KEY)
echo "📍 Dirección del deployer: $DEPLOYER_ADDRESS"
echo ""

# Verificar balance
echo "💰 Verificando balance en Fuji..."
BALANCE=$(cast balance $DEPLOYER_ADDRESS --rpc-url $FUJI_RPC_URL)
BALANCE_ETH=$(cast --to-unit $BALANCE ether)

echo "   Balance: $BALANCE_ETH AVAX"
echo ""

if [ "$(echo "$BALANCE_ETH < 0.1" | bc)" -eq 1 ]; then
  echo "❌ Balance insuficiente. Necesitas al menos 0.1 AVAX en Fuji testnet."
  echo ""
  echo "🎁 Obtén AVAX testnet gratis en:"
  echo "   https://faucet.avax.network/"
  echo "   https://core.app/tools/testnet-faucet/"
  echo ""
  exit 1
fi

# Ir al directorio de contratos
cd contracts

# Verificar dependencias de Foundry
if [ ! -d "lib/forge-std" ]; then
  echo "📦 Instalando dependencias de Foundry..."
  forge install foundry-rs/forge-std --no-commit
  echo ""
fi

# Compilar contratos
echo "🔨 Compilando contratos..."
forge build
echo ""

# Confirmación antes de desplegar
echo "🚨 CONFIRMACIÓN:"
echo "   Network: Avalanche Fuji Testnet"
echo "   Chain ID: $FUJI_CHAIN_ID"
echo "   RPC URL: $FUJI_RPC_URL"
echo "   Deployer: $DEPLOYER_ADDRESS"
echo "   Balance: $BALANCE_ETH AVAX"
echo ""
read -p "¿Proceder con el despliegue? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "❌ Despliegue cancelado por el usuario."
  exit 1
fi

# Desplegar contratos
echo ""
echo "📤 Desplegando contratos en Fuji..."
echo "   Esto puede tomar 1-2 minutos..."
echo ""

forge script script/Deploy.s.sol \
  --rpc-url $FUJI_RPC_URL \
  --broadcast \
  --private-key $PRIVATE_KEY \
  --legacy \
  -vvv

DEPLOY_STATUS=$?

echo ""

if [ $DEPLOY_STATUS -eq 0 ]; then
  echo "✅ Contratos desplegados exitosamente en Fuji!"
  echo ""

  # Volver al directorio raíz
  cd ..

  echo "📋 Las direcciones de los contratos se encuentran en:"
  echo "   contracts/broadcast/Deploy.s.sol/43113/run-latest.json"
  echo ""

  # Intentar extraer y mostrar las direcciones
  if [ -f "contracts/broadcast/Deploy.s.sol/43113/run-latest.json" ]; then
    echo "📝 Direcciones desplegadas:"
    echo ""

    # Usar jq si está disponible, sino usar grep/sed básico
    if command -v jq &> /dev/null; then
      jq -r '.transactions[] | select(.contractName != null) | "   \(.contractName): \(.contractAddress)"' \
        contracts/broadcast/Deploy.s.sol/43113/run-latest.json
    else
      grep -o '"contractName":"[^"]*","contractAddress":"[^"]*"' \
        contracts/broadcast/Deploy.s.sol/43113/run-latest.json | \
        sed 's/"contractName":"\([^"]*\)","contractAddress":"\([^"]*\)"/   \1: \2/g'
    fi

    echo ""
    echo "🔍 Verifica tus contratos en Snowtrace Testnet:"
    echo "   https://testnet.snowtrace.io/"
    echo ""
  fi

  echo "💡 Para actualizar tu configuración local:"
  echo "   1. Copia las direcciones de arriba"
  echo "   2. Actualiza deployment.json con las nuevas direcciones"
  echo "   3. Actualiza src/contracts/config.ts si usas el frontend"
  echo "   4. Actualiza RPC_URL y CHAIN_ID en .env:"
  echo "      RPC_URL=$FUJI_RPC_URL"
  echo "      CHAIN_ID=$FUJI_CHAIN_ID"
  echo ""
else
  echo "❌ Error al desplegar contratos. Revisa los logs arriba."
  cd ..
  exit 1
fi
