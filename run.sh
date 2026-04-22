#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Run with project-local virtual environment when available.
if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/main.py"
elif [ -x "$SCRIPT_DIR/vnev/bin/python" ]; then
    exec "$SCRIPT_DIR/vnev/bin/python" "$SCRIPT_DIR/main.py"
else
    exec python3 "$SCRIPT_DIR/main.py"
fi
