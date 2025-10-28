@echo off
REM Run script for craami agent

cd /d "%~dp0"

REM Activate virtual environment if exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Run agent
python main.py
