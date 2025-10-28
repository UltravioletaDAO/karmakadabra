@echo off
REM Start Karmacadabra agent stack with Docker Compose (Windows)

echo Starting Karmacadabra Agent Stack...

REM Check if .env files exist
set MISSING_ENV=0
for %%a in (validator karma-hello abracadabra skill-extractor voice-extractor) do (
    if not exist "agents\%%a\.env" (
        echo [ERROR] Missing agents\%%a\.env
        set MISSING_ENV=1
    )
)

if %MISSING_ENV%==1 (
    echo.
    echo Create .env files from .env.example:
    echo    copy agents\validator\.env.example agents\validator\.env
    echo    copy agents\karma-hello\.env.example agents\karma-hello\.env
    echo    copy agents\abracadabra\.env.example agents\abracadabra\.env
    echo    copy agents\skill-extractor\.env.example agents\skill-extractor\.env
    echo    copy agents\voice-extractor\.env.example agents\voice-extractor\.env
    echo.
    echo    Then edit each .env file with your configuration.
    exit /b 1
)

REM Check if AWS credentials exist
if not exist "%USERPROFILE%\.aws\credentials" (
    echo [WARNING] AWS credentials not found at %USERPROFILE%\.aws\credentials
    echo Agents will not be able to fetch private keys from AWS Secrets Manager
    echo You can either:
    echo 1. Configure AWS CLI: aws configure
    echo 2. Add PRIVATE_KEY to each .env file for testing only
    echo.
    choice /C YN /M "Continue anyway"
    if errorlevel 2 exit /b 1
)

REM Determine which compose file to use
if "%1"=="dev" (
    echo Starting in DEVELOPMENT mode hot reload enabled
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
) else (
    echo Starting in PRODUCTION mode
    docker-compose up -d
)

echo.
echo [OK] Agent stack started!
echo.
echo Service Status:
docker-compose ps

echo.
echo Agent Endpoints:
echo    Validator:        http://localhost:9001/health
echo    Karma-Hello:      http://localhost:9002/health
echo    Abracadabra:      http://localhost:9003/health
echo    Skill-Extractor:  http://localhost:9004/health
echo    Voice-Extractor:  http://localhost:9005/health
echo.
echo Metrics:
echo    Validator:        http://localhost:9090/metrics
echo.
echo View Logs:
echo    All agents:       docker-compose logs -f
echo    Single agent:     docker-compose logs -f karma-hello
echo.
echo Stop Stack:
echo    docker-compose down
