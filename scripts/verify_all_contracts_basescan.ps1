# PowerShell script to verify all Base Sepolia contracts on Basescan
# Requires: BASESCAN_API_KEY environment variable
# Usage: .\scripts\verify_all_contracts_basescan.ps1

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Base Sepolia Contract Verification" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if API key is set
if (-not $env:BASESCAN_API_KEY) {
    Write-Host "[ERROR] BASESCAN_API_KEY not set" -ForegroundColor Red
    Write-Host ""
    Write-Host "Get API key from: https://basescan.org/myapikey"
    Write-Host "Then run: `$env:BASESCAN_API_KEY='your-api-key'"
    Write-Host ""
    exit 1
}

Write-Host "[OK] BASESCAN_API_KEY is set" -ForegroundColor Green
Write-Host ""

# Contract addresses
$GLUE_TOKEN = "0xfEe5CC33479E748f40F5F299Ff6494b23F88C425"
$IDENTITY_REGISTRY = "0x8a20f665c02a33562a0462a0908a64716Ed7463d"
$REPUTATION_REGISTRY = "0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F"
$VALIDATION_REGISTRY = "0x3C545DBeD1F587293fA929385442A459c2d316c4"

# Verify GLUE Token
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "[1/4] Verifying GLUE Token..." -ForegroundColor Yellow
Write-Host "Address: $GLUE_TOKEN"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location erc-20

forge verify-contract `
  $GLUE_TOKEN `
  src/GLUE.sol:GLUE `
  --chain base-sepolia `
  --watch

if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] GLUE verification failed or already verified" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[OK] GLUE Token verification complete" -ForegroundColor Green
Write-Host ""

Set-Location ..

# Verify Identity Registry
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "[2/4] Verifying Identity Registry..." -ForegroundColor Yellow
Write-Host "Address: $IDENTITY_REGISTRY"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location erc-8004/contracts

forge verify-contract `
  $IDENTITY_REGISTRY `
  src/IdentityRegistry.sol:IdentityRegistry `
  --chain base-sepolia `
  --watch

if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] IdentityRegistry verification failed or already verified" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[OK] Identity Registry verification complete" -ForegroundColor Green
Write-Host ""

# Verify Reputation Registry
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "[3/4] Verifying Reputation Registry..." -ForegroundColor Yellow
Write-Host "Address: $REPUTATION_REGISTRY"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

forge verify-contract `
  $REPUTATION_REGISTRY `
  src/ReputationRegistry.sol:ReputationRegistry `
  --chain base-sepolia `
  --watch

if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] ReputationRegistry verification failed or already verified" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[OK] Reputation Registry verification complete" -ForegroundColor Green
Write-Host ""

# Verify Validation Registry
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "[4/4] Verifying Validation Registry..." -ForegroundColor Yellow
Write-Host "Address: $VALIDATION_REGISTRY"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

forge verify-contract `
  $VALIDATION_REGISTRY `
  src/ValidationRegistry.sol:ValidationRegistry `
  --chain base-sepolia `
  --watch

if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] ValidationRegistry verification failed or already verified" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[OK] Validation Registry verification complete" -ForegroundColor Green
Write-Host ""

Set-Location ../..

# Summary
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "VERIFICATION COMPLETE" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Check verified contracts at:"
Write-Host "  GLUE Token:           https://sepolia.basescan.org/address/$GLUE_TOKEN"
Write-Host "  Identity Registry:    https://sepolia.basescan.org/address/$IDENTITY_REGISTRY"
Write-Host "  Reputation Registry:  https://sepolia.basescan.org/address/$REPUTATION_REGISTRY"
Write-Host "  Validation Registry:  https://sepolia.basescan.org/address/$VALIDATION_REGISTRY"
Write-Host ""
