#!/bin/bash

# Script para desplegar los contratos ERC-8004 en Base Sepolia Testnet

set -e

echo "[*] Desplegando contratos ERC-8004 en Base Sepolia Testnet..."
echo ""

# Configuración de Base Sepolia
BASE_SEPOLIA_RPC_URL="https://base-sepolia.g.alchemy.com/v2/demo"
BASE_SEPOLIA_CHAIN_ID=84532
EXPLORER_URL="https://sepolia.basescan.org"

# Verificar que se proporcione la private key
if [ -z "$PRIVATE_KEY" ]; then
  echo "[!] La variable de entorno PRIVATE_KEY no está configurada."
  echo ""
  echo "Intentando obtener desde AWS Secrets Manager..."

  PRIVATE_KEY=$(aws secretsmanager get-secret-value \
    --secret-id karmacadabra \
    --region us-east-1 \
    --query 'SecretString' \
    --output text | python -c "import sys, json; print(json.load(sys.stdin)['erc-20']['private_key'])")

  if [ -z "$PRIVATE_KEY" ]; then
    echo "[-] Error: No se pudo obtener la private key"
    exit 1
  fi

  echo "[+] Private key obtenida desde AWS"
  export PRIVATE_KEY
fi

# Derivar la dirección de la private key
DEPLOYER_ADDRESS=$(cast wallet address $PRIVATE_KEY)
echo "[*] Dirección del deployer: $DEPLOYER_ADDRESS"
echo ""

# Verificar balance
echo "[*] Verificando balance en Base Sepolia..."
BALANCE=$(cast balance $DEPLOYER_ADDRESS --rpc-url $BASE_SEPOLIA_RPC_URL)
BALANCE_ETH=$(cast --to-unit $BALANCE ether)

echo "   Balance: $BALANCE_ETH ETH"
echo ""

if [ "$(echo "$BALANCE_ETH < 0.01" | bc)" -eq 1 ]; then
  echo "[-] Balance insuficiente. Necesitas al menos 0.01 ETH en Base Sepolia testnet."
  echo ""
  echo "[!] Obtén ETH testnet gratis en:"
  echo "   https://www.alchemy.com/faucets/base-sepolia"
  echo "   https://bridge.base.org/"
  echo ""
  exit 1
fi

# Ir al directorio de contratos
cd contracts

# Verificar dependencias de Foundry
if [ ! -d "lib/forge-std" ]; then
  echo "[*] Instalando dependencias de Foundry..."
  forge install foundry-rs/forge-std --no-commit
  echo ""
fi

# Compilar contratos
echo "[*] Compilando contratos..."
forge build
echo ""

# Confirmación antes de desplegar
echo "[!] CONFIRMACION:"
echo "   Network: Base Sepolia Testnet"
echo "   Chain ID: $BASE_SEPOLIA_CHAIN_ID"
echo "   RPC URL: $BASE_SEPOLIA_RPC_URL"
echo "   Deployer: $DEPLOYER_ADDRESS"
echo "   Balance: $BALANCE_ETH ETH"
echo ""
read -p "Proceder con el despliegue? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "[-] Despliegue cancelado por el usuario."
  exit 1
fi

# Desplegar contratos
echo ""
echo "[*] Desplegando contratos en Base Sepolia..."
echo "   Esto puede tomar 1-2 minutos..."
echo ""

forge script script/Deploy.s.sol \
  --rpc-url $BASE_SEPOLIA_RPC_URL \
  --broadcast \
  --private-key $PRIVATE_KEY \
  --verify \
  --etherscan-api-key $BASESCAN_API_KEY \
  --verifier-url https://api-sepolia.basescan.org/api \
  --legacy \
  -vvv

DEPLOY_STATUS=$?

echo ""

if [ $DEPLOY_STATUS -eq 0 ]; then
  echo "[+] Contratos desplegados exitosamente en Base Sepolia!"
  echo ""

  # Volver al directorio raíz
  cd ..

  echo "[*] Las direcciones de los contratos se encuentran en:"
  echo "   contracts/broadcast/Deploy.s.sol/$BASE_SEPOLIA_CHAIN_ID/run-latest.json"
  echo ""

  # Intentar extraer y mostrar las direcciones
  BROADCAST_FILE="contracts/broadcast/Deploy.s.sol/$BASE_SEPOLIA_CHAIN_ID/run-latest.json"

  if [ -f "$BROADCAST_FILE" ]; then
    echo "[*] Direcciones desplegadas:"
    echo ""

    # Usar jq si está disponible
    if command -v jq &> /dev/null; then
      IDENTITY_REGISTRY=$(jq -r '.transactions[] | select(.contractName == "IdentityRegistry") | .contractAddress' $BROADCAST_FILE | head -n 1)
      REPUTATION_REGISTRY=$(jq -r '.transactions[] | select(.contractName == "ReputationRegistry") | .contractAddress' $BROADCAST_FILE | head -n 1)
      VALIDATION_REGISTRY=$(jq -r '.transactions[] | select(.contractName == "ValidationRegistry") | .contractAddress' $BROADCAST_FILE | head -n 1)

      echo "   IdentityRegistry: $IDENTITY_REGISTRY"
      echo "   ReputationRegistry: $REPUTATION_REGISTRY"
      echo "   ValidationRegistry: $VALIDATION_REGISTRY"
      echo ""

      # Guardar en .env.base-sepolia
      cat > .env.base-sepolia <<EOF
# Base Sepolia Deployment - ERC-8004 Registries
NETWORK=base-sepolia
CHAIN_ID=$BASE_SEPOLIA_CHAIN_ID
IDENTITY_REGISTRY=$IDENTITY_REGISTRY
REPUTATION_REGISTRY=$REPUTATION_REGISTRY
VALIDATION_REGISTRY=$VALIDATION_REGISTRY
RPC_URL=$BASE_SEPOLIA_RPC_URL
EXPLORER_URL=$EXPLORER_URL
EOF

      echo "[+] Deployment info saved to .env.base-sepolia"
      echo ""
    else
      grep -o '"contractName":"[^"]*","contractAddress":"[^"]*"' $BROADCAST_FILE | \
        sed 's/"contractName":"\([^"]*\)","contractAddress":"\([^"]*\)"/   \1: \2/g'
    fi

    echo ""
    echo "[*] Verifica tus contratos en Base Sepolia Explorer:"
    echo "   $EXPLORER_URL/"
    echo ""
  fi

  echo "[!] Para actualizar tu configuración local:"
  echo "   1. Copia las direcciones de arriba"
  echo "   2. Actualiza shared/contracts_config.py con las nuevas direcciones"
  echo "   3. Actualiza RPC_URL y CHAIN_ID en configuración de agentes"
  echo ""
else
  echo "[-] Error al desplegar contratos. Revisa los logs arriba."
  cd ..
  exit 1
fi
