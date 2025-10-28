@echo off
REM Script para desplegar los contratos ERC-8004 en Avalanche Fuji Testnet - Windows

setlocal enabledelayedexpansion

echo.
echo 🏔️  Desplegando contratos ERC-8004 en Avalanche Fuji Testnet...
echo.

REM Configuración de Fuji
set FUJI_RPC_URL=https://avalanche-fuji-c-chain-rpc.publicnode.com
set FUJI_CHAIN_ID=43113

REM Verificar que se proporcione la private key
if "%PRIVATE_KEY%"=="" (
  echo ⚠️  La variable de entorno PRIVATE_KEY no está configurada.
  echo.
  echo Por favor, configura tu private key:
  echo   set PRIVATE_KEY=0x...
  echo.
  echo O créala en un archivo .env.fuji y carga las variables
  echo.
  exit /b 1
)

REM Advertencia de seguridad
echo ⚠️  ADVERTENCIA DE SEGURIDAD:
echo    - Asegúrate de usar una wallet de PRUEBA
echo    - NUNCA uses una private key con fondos reales
echo    - Esta transacción se ejecutará en Fuji TESTNET
echo.

REM Derivar la dirección de la private key
for /f "tokens=*" %%a in ('cast wallet address %PRIVATE_KEY%') do set DEPLOYER_ADDRESS=%%a
echo 📍 Dirección del deployer: %DEPLOYER_ADDRESS%
echo.

REM Verificar balance
echo 💰 Verificando balance en Fuji...
for /f "tokens=*" %%a in ('cast balance %DEPLOYER_ADDRESS% --rpc-url %FUJI_RPC_URL%') do set BALANCE=%%a

echo    Balance: %BALANCE% wei
echo.

REM Nota: En Windows es más difícil comparar balances, así que lo dejamos informativo
echo ⚠️  Asegúrate de tener al menos 0.1 AVAX en Fuji testnet
echo.
echo 🎁 Obtén AVAX testnet gratis en:
echo    https://faucet.avax.network/
echo    https://core.app/tools/testnet-faucet/
echo.

REM Ir al directorio de contratos
cd contracts

REM Verificar dependencias de Foundry
if not exist "lib\forge-std" (
  echo 📦 Instalando dependencias de Foundry...
  forge install foundry-rs/forge-std --no-commit
  echo.
)

REM Compilar contratos
echo 🔨 Compilando contratos...
forge build
echo.

REM Confirmación antes de desplegar
echo 🚨 CONFIRMACIÓN:
echo    Network: Avalanche Fuji Testnet
echo    Chain ID: %FUJI_CHAIN_ID%
echo    RPC URL: %FUJI_RPC_URL%
echo    Deployer: %DEPLOYER_ADDRESS%
echo.
set /p CONFIRM="¿Proceder con el despliegue? (y/N): "

if /i not "%CONFIRM%"=="y" (
  echo ❌ Despliegue cancelado por el usuario.
  cd ..
  exit /b 1
)

REM Desplegar contratos
echo.
echo 📤 Desplegando contratos en Fuji...
echo    Esto puede tomar 1-2 minutos...
echo.

forge script script/Deploy.s.sol --rpc-url %FUJI_RPC_URL% --broadcast --private-key %PRIVATE_KEY% --legacy -vvv

if errorlevel 1 (
  echo.
  echo ❌ Error al desplegar contratos. Revisa los logs arriba.
  cd ..
  exit /b 1
)

echo.
echo ✅ Contratos desplegados exitosamente en Fuji!
echo.

REM Volver al directorio raíz
cd ..

echo 📋 Las direcciones de los contratos se encuentran en:
echo    contracts\broadcast\Deploy.s.sol\43113\run-latest.json
echo.

if exist "contracts\broadcast\Deploy.s.sol\43113\run-latest.json" (
  echo 📝 Revisa el archivo run-latest.json para ver las direcciones desplegadas
  echo.
  echo 🔍 Verifica tus contratos en Snowtrace Testnet:
  echo    https://testnet.snowtrace.io/
  echo.
)

echo 💡 Para actualizar tu configuración local:
echo    1. Revisa contracts\broadcast\Deploy.s.sol\43113\run-latest.json
echo    2. Actualiza deployment.json con las nuevas direcciones
echo    3. Actualiza src\contracts\config.ts si usas el frontend
echo    4. Actualiza RPC_URL y CHAIN_ID en .env:
echo       RPC_URL=%FUJI_RPC_URL%
echo       CHAIN_ID=%FUJI_CHAIN_ID%
echo.
