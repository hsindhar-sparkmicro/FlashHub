#!/bin/bash
# FlashHub — start the web server (no display required)

cd "$(dirname "$0")"

# Activate virtual environment
if [ -d "vnev" ]; then
    source vnev/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

HOST="${FLASHHUB_HOST:-127.0.0.1}"
PORT="${FLASHHUB_PORT:-8000}"
CONFIG="${FLASHHUB_CONFIG:-config.json}"

echo ""
echo "  Starting FlashHub Web Server..."
echo "  Open in your browser (or via VS Code port forward):"
echo "  → http://${HOST}:${PORT}"
echo ""

python web_server.py --host "$HOST" --port "$PORT" --config "$CONFIG" "$@"
