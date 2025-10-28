# Run script for cyberpaisa agent (PowerShell)

# Change to script directory
Set-Location $PSScriptRoot

# Check if venv exists
if (-not (Test-Path "venv")) {
    Write-Host "ERROR: Virtual environment not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please run setup first:" -ForegroundColor Yellow
    Write-Host "  .\setup.ps1" -ForegroundColor White
    Write-Host ""
    Write-Host "Or use batch file:" -ForegroundColor Yellow
    Write-Host "  setup.bat" -ForegroundColor White
    Write-Host ""
    pause
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

# Check if .env is configured
$envContent = Get-Content .env -Raw
if ($envContent -match "PRIVATE_KEY=\s*$") {
    Write-Host ""
    Write-Host "WARNING: PRIVATE_KEY not configured in .env" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please configure your wallet:" -ForegroundColor Cyan
    Write-Host "  1. python ..\..\scripts\generate-wallet.py" -ForegroundColor White
    Write-Host "  2. Add PRIVATE_KEY to .env" -ForegroundColor White
    Write-Host "  3. Fund wallet with AVAX and GLUE" -ForegroundColor White
    Write-Host ""
    Write-Host "Or run automated setup:" -ForegroundColor Cyan
    Write-Host "  python ..\..\scripts\setup_user_agent.py cyberpaisa" -ForegroundColor White
    Write-Host ""
    pause
}

# Run agent
Write-Host ""
Write-Host "Starting cyberpaisa agent on port 9030..." -ForegroundColor Green
Write-Host ""
python main.py
