@echo off
REM Run script for cyberpaisa agent

cd /d "%~dp0"

REM Check if venv exists
if not exist venv (
    echo [31mERROR: Virtual environment not found[0m
    echo.
    echo Please run setup.bat first:
    echo   setup.bat
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if .env is configured
findstr /C:"PRIVATE_KEY=" .env | findstr /V /C:"PRIVATE_KEY=$" > nul
if errorlevel 1 (
    echo.
    echo [33mWARNING: PRIVATE_KEY not configured in .env[0m
    echo.
    echo Please configure your wallet:
    echo   1. python ..\..\scripts\generate-wallet.py
    echo   2. Add PRIVATE_KEY to .env
    echo   3. Fund wallet with AVAX and GLUE
    echo.
    echo Or run automated setup:
    echo   python ..\..\scripts\setup_user_agent.py cyberpaisa
    echo.
    pause
)

REM Run agent
echo.
echo Starting cyberpaisa agent on port 9030...
echo.
python main.py
