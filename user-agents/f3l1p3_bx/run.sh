#!/bin/bash
# Run script for f3l1p3_bx agent

cd "$(dirname "$0")"

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run agent
python main.py
