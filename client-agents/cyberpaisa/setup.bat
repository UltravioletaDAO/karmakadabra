@echo off
REM Quick setup for cyberpaisa agent

echo ========================================
echo SETUP CYBERPAISA AGENT
echo ========================================

cd /d "%~dp0"

REM Check if venv exists
if not exist venv (
    echo.
    echo Creating virtual environment...
    python -m venv venv

    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        echo Make sure Python 3.11+ is installed
        pause
        exit /b 1
    )

    echo [32mVirtual environment created![0m
)

REM Activate venv
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [31mERROR: Failed to install dependencies[0m
    pause
    exit /b 1
)

echo.
echo ========================================
echo [32mSETUP COMPLETE![0m
echo ========================================
echo.
echo To run the agent:
echo   1. run.bat
echo.
echo To run tests:
echo   2. cd ..\..
echo   3. python tests\test_cyberpaisa_client.py
echo.
pause
