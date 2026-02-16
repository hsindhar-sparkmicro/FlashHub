#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

# Check if virtual environment exists and activate it
if [ -d ".venv" ]; then
    echo "Activating .venv virtual environment..."
    source .venv/bin/activate
elif [ -d "vnev" ]; then
    echo "Activating vnev virtual environment..."
    source vnev/bin/activate
else
    echo "No virtual environment found. Running with system Python..."
fi

# Run the main application
python3 main.py
