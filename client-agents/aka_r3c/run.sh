#!/bin/bash
# Run script for aka_r3c agent

cd "$(dirname "$0")"

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run agent
python main.py
