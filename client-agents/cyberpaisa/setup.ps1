# Quick setup for cyberpaisa agent
# PowerShell version

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SETUP CYBERPAISA AGENT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to script directory
Set-Location $PSScriptRoot

# Check if venv exists
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        Write-Host "Make sure Python 3.11+ is installed" -ForegroundColor Red
        pause
        exit 1
    }

    Write-Host "Virtual environment created!" -ForegroundColor Green
}

# Activate venv
Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Yellow

# For PowerShell
& ".\venv\Scripts\Activate.ps1"

# Upgrade pip
Write-Host ""
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "SETUP COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "To run the agent:" -ForegroundColor Cyan
Write-Host "  1. .\run.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To run tests:" -ForegroundColor Cyan
Write-Host "  2. cd ..\.." -ForegroundColor White
Write-Host "  3. python tests\test_cyberpaisa_client.py" -ForegroundColor White
Write-Host ""
pause
