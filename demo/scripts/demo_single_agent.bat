@echo off
REM Quick demo: Test a single agent locally
REM No wallet/AVAX needed - just tests HTTP endpoints

echo ==========================================
echo Single Agent Demo - elboorja
echo ==========================================
echo.
echo Starting elboorja agent on port 9044...
echo.

cd user-agents\elboorja

echo Note: Agent will skip blockchain registration for this demo
echo.

REM Start agent in background
start /B python main.py

echo Waiting 5 seconds for agent to start...
timeout /t 5 /nobreak >nul

echo.
echo ==========================================
echo Testing Agent Endpoints
echo ==========================================
echo.

echo 1. Health Check:
curl -s http://localhost:9044/health
echo.
echo.

echo 2. A2A Protocol Agent Card:
curl -s http://localhost:9044/.well-known/agent-card
echo.
echo.

echo 3. Service Listing:
curl -s http://localhost:9044/services
echo.
echo.

echo 4. User Profile:
curl -s http://localhost:9044/profile
echo.
echo.

echo ==========================================
echo Demo Complete!
echo ==========================================
echo.
echo To stop the agent: taskkill /F /IM python.exe
echo Or close the Python window manually
echo.
pause
