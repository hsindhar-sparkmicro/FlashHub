#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
XDG_APPS_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}"
if [[ "$XDG_APPS_ROOT" == "$HOME/snap/"* ]]; then
    XDG_APPS_ROOT="$HOME/.local/share"
fi
APPLICATIONS_DIR="$XDG_APPS_ROOT/applications"
DESKTOP_DIR="$HOME/Desktop"
LAUNCHER_PATH="$APPLICATIONS_DIR/FlashHub.desktop"

mkdir -p "$APPLICATIONS_DIR"

if [ -x "$SCRIPT_DIR/dist/FlashHub" ]; then
    EXEC_PATH="$SCRIPT_DIR/launch_gui.sh"
else
    EXEC_PATH="$SCRIPT_DIR/launch_gui.sh"
fi

chmod +x "$SCRIPT_DIR/launch_gui.sh"

cat > "$LAUNCHER_PATH" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=FlashHub
Comment=STM32 firmware flasher
Exec=$EXEC_PATH
Path=$SCRIPT_DIR
Icon=$SCRIPT_DIR/images/flashhub_icon.svg
Terminal=false
Categories=Development;Electronics;
StartupNotify=true
StartupWMClass=FlashHub
EOF

chmod +x "$LAUNCHER_PATH"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

if [ -d "$DESKTOP_DIR" ]; then
    cp "$LAUNCHER_PATH" "$DESKTOP_DIR/FlashHub.desktop"
    chmod +x "$DESKTOP_DIR/FlashHub.desktop"
fi

echo "Installed launcher: $LAUNCHER_PATH"
if [ -d "$DESKTOP_DIR" ]; then
    echo "Copied desktop shortcut: $DESKTOP_DIR/FlashHub.desktop"
    echo "If Ubuntu still shows it as untrusted, right-click it once and choose 'Allow Launching'."
fi
echo "For terminal launch from the repo, use: $SCRIPT_DIR/FlashHub"