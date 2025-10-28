# Script para desplegar los contratos ERC-8004 en Avalanche Fuji Testnet - PowerShell

# Detener en caso de error
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "🏔️  Desplegando contratos ERC-8004 en Avalanche Fuji Testnet..." -ForegroundColor Cyan
Write-Host ""

# Configuración de Fuji
$FUJI_RPC_URL = "https://avalanche-fuji-c-chain-rpc.publicnode.com"
$FUJI_CHAIN_ID = 43113

# Verificar que se proporcione la private key
if (-not $env:PRIVATE_KEY) {
    Write-Host "⚠️  La variable de entorno PRIVATE_KEY no está configurada." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Por favor, configura tu private key:"
    Write-Host '  $env:PRIVATE_KEY = "0x..."' -ForegroundColor Gray
    Write-Host ""
    Write-Host "O créala en un archivo .env.fuji.ps1:" -ForegroundColor Gray
    Write-Host '  $env:PRIVATE_KEY = "0x..."' -ForegroundColor Gray
    Write-Host "  Y luego ejecuta: . .\.env.fuji.ps1" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

# Advertencia de seguridad
Write-Host "⚠️  ADVERTENCIA DE SEGURIDAD:" -ForegroundColor Yellow
Write-Host "   - Asegúrate de usar una wallet de PRUEBA"
Write-Host "   - NUNCA uses una private key con fondos reales"
Write-Host "   - Esta transacción se ejecutará en Fuji TESTNET"
Write-Host ""

# Derivar la dirección de la private key
try {
    $DEPLOYER_ADDRESS = cast wallet address $env:PRIVATE_KEY
    Write-Host "📍 Dirección del deployer: $DEPLOYER_ADDRESS" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "❌ Error al derivar la dirección. Verifica que la PRIVATE_KEY sea válida." -ForegroundColor Red
    exit 1
}

# Verificar balance
Write-Host "💰 Verificando balance en Fuji..." -ForegroundColor Cyan
try {
    $BALANCE = cast balance $DEPLOYER_ADDRESS --rpc-url $FUJI_RPC_URL
    $BALANCE_ETH = cast --to-unit $BALANCE ether

    Write-Host "   Balance: $BALANCE_ETH AVAX" -ForegroundColor Green
    Write-Host ""

    # Convertir a número para comparar
    $BalanceNum = [double]$BALANCE_ETH

    if ($BalanceNum -lt 0.1) {
        Write-Host "❌ Balance insuficiente. Necesitas al menos 0.1 AVAX en Fuji testnet." -ForegroundColor Red
        Write-Host ""
        Write-Host "🎁 Obtén AVAX testnet gratis en:" -ForegroundColor Yellow
        Write-Host "   https://faucet.avax.network/"
        Write-Host "   https://core.app/tools/testnet-faucet/"
        Write-Host ""
        exit 1
    }
} catch {
    Write-Host "⚠️  No se pudo verificar el balance. Continuando..." -ForegroundColor Yellow
    Write-Host "   Asegúrate de tener al menos 0.1 AVAX en Fuji testnet" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "🎁 Obtén AVAX testnet gratis en:" -ForegroundColor Yellow
    Write-Host "   https://faucet.avax.network/"
    Write-Host "   https://core.app/tools/testnet-faucet/"
    Write-Host ""
}

# Ir al directorio de contratos
Push-Location contracts

# Verificar dependencias de Foundry
if (-not (Test-Path "lib\forge-std")) {
    Write-Host "📦 Instalando dependencias de Foundry..." -ForegroundColor Cyan
    forge install foundry-rs/forge-std --no-commit
    Write-Host ""
}

# Compilar contratos
Write-Host "🔨 Compilando contratos..." -ForegroundColor Cyan
forge build
Write-Host ""

# Confirmación antes de desplegar
Write-Host "🚨 CONFIRMACIÓN:" -ForegroundColor Yellow
Write-Host "   Network: Avalanche Fuji Testnet"
Write-Host "   Chain ID: $FUJI_CHAIN_ID"
Write-Host "   RPC URL: $FUJI_RPC_URL"
Write-Host "   Deployer: $DEPLOYER_ADDRESS"
if ($BALANCE_ETH) {
    Write-Host "   Balance: $BALANCE_ETH AVAX"
}
Write-Host ""

$confirmation = Read-Host "¿Proceder con el despliegue? (y/N)"

if ($confirmation -ne 'y' -and $confirmation -ne 'Y') {
    Write-Host "❌ Despliegue cancelado por el usuario." -ForegroundColor Red
    Pop-Location
    exit 1
}

# Desplegar contratos
Write-Host ""
Write-Host "📤 Desplegando contratos en Fuji..." -ForegroundColor Cyan
Write-Host "   Esto puede tomar 1-2 minutos..." -ForegroundColor Gray
Write-Host ""

try {
    forge script script/Deploy.s.sol `
        --rpc-url $FUJI_RPC_URL `
        --broadcast `
        --private-key $env:PRIVATE_KEY `
        --legacy `
        -vvv

    if ($LASTEXITCODE -ne 0) {
        throw "Forge script falló con código de salida $LASTEXITCODE"
    }

    Write-Host ""
    Write-Host "✅ Contratos desplegados exitosamente en Fuji!" -ForegroundColor Green
    Write-Host ""

    # Volver al directorio raíz
    Pop-Location

    Write-Host "📋 Las direcciones de los contratos se encuentran en:" -ForegroundColor Cyan
    Write-Host "   contracts\broadcast\Deploy.s.sol\43113\run-latest.json" -ForegroundColor Gray
    Write-Host ""

    # Intentar extraer y mostrar las direcciones
    $broadcastFile = "contracts\broadcast\Deploy.s.sol\43113\run-latest.json"
    if (Test-Path $broadcastFile) {
        Write-Host "📝 Direcciones desplegadas:" -ForegroundColor Cyan
        Write-Host ""

        try {
            $broadcast = Get-Content $broadcastFile | ConvertFrom-Json

            foreach ($tx in $broadcast.transactions) {
                if ($tx.contractName -and $tx.contractAddress) {
                    Write-Host "   $($tx.contractName): $($tx.contractAddress)" -ForegroundColor Green
                }
            }

            Write-Host ""
            Write-Host "🔍 Verifica tus contratos en Snowtrace Testnet:" -ForegroundColor Cyan
            Write-Host "   https://testnet.snowtrace.io/" -ForegroundColor Blue
            Write-Host ""
        } catch {
            Write-Host "⚠️  No se pudieron extraer las direcciones automáticamente." -ForegroundColor Yellow
            Write-Host "   Revisa el archivo run-latest.json manualmente." -ForegroundColor Yellow
            Write-Host ""
        }
    }

    Write-Host "💡 Para actualizar tu configuración local:" -ForegroundColor Cyan
    Write-Host "   1. Copia las direcciones de arriba"
    Write-Host "   2. Actualiza deployment.json con las nuevas direcciones"
    Write-Host "   3. Actualiza src\contracts\config.ts si usas el frontend"
    Write-Host "   4. Actualiza RPC_URL y CHAIN_ID en .env:"
    Write-Host "      RPC_URL=$FUJI_RPC_URL" -ForegroundColor Gray
    Write-Host "      CHAIN_ID=$FUJI_CHAIN_ID" -ForegroundColor Gray
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "❌ Error al desplegar contratos:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Pop-Location
    exit 1
}
