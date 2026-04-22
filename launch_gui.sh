#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -x "$SCRIPT_DIR/dist/FlashHub" ]; then
    APP_CMD=("$SCRIPT_DIR/dist/FlashHub")
else
    APP_CMD=("$SCRIPT_DIR/run.sh")
fi

nohup "${APP_CMD[@]}" >/dev/null 2>&1 &
