@echo off
REM Run script for 0xdream_sgo agent

cd /d "%~dp0"

REM Activate virtual environment if exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Run agent
python main.py
