#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

# --------------------------------------------------------------------------
# DISPLAY handling for VS Code Remote SSH (or any headless SSH session)
# --------------------------------------------------------------------------

# Check if libxcb-cursor0 is installed (required by Qt 6.5+)
if ! dpkg -s libxcb-cursor0 &>/dev/null; then
    echo "[run-ssh] libxcb-cursor0 not found. Installing..."
    sudo apt-get install -y libxcb-cursor0
fi

if [ -n "$DISPLAY" ]; then
    # A real display is already available (e.g. X11 forwarding is active)
    echo "[run-ssh] DISPLAY=$DISPLAY already set, using it."

elif [ -n "$WAYLAND_DISPLAY" ]; then
    # Wayland compositor is available
    echo "[run-ssh] Wayland display detected, setting QT_QPA_PLATFORM=wayland."
    export QT_QPA_PLATFORM=wayland

elif command -v Xvfb &>/dev/null; then
    # Fall back to a virtual framebuffer
    VDISPLAY=:99
    if ! pgrep -f "Xvfb $VDISPLAY" &>/dev/null; then
        echo "[run-ssh] Starting Xvfb on $VDISPLAY..."
        Xvfb "$VDISPLAY" -screen 0 1920x1080x24 &
        XVFB_PID=$!
        sleep 1   # give Xvfb a moment to start
        echo "[run-ssh] Xvfb started (PID $XVFB_PID)."
    else
        echo "[run-ssh] Xvfb already running on $VDISPLAY."
    fi
    export DISPLAY=$VDISPLAY

else
    # Last resort: offscreen rendering (no visible window)
    echo "[run-ssh] No display or Xvfb found. Falling back to offscreen rendering."
    echo "[run-ssh] Install xvfb for a virtual framebuffer: sudo apt install xvfb"
    export QT_QPA_PLATFORM=offscreen
fi

# --------------------------------------------------------------------------
# Activate virtual environment (mirrors run.sh logic)
# --------------------------------------------------------------------------
if [ -d ".venv" ]; then
    echo "[run-ssh] Activating .venv virtual environment..."
    source .venv/bin/activate
elif [ -d "vnev" ]; then
    echo "[run-ssh] Activating vnev virtual environment..."
    source vnev/bin/activate
else
    echo "[run-ssh] No virtual environment found. Running with system Python..."
fi

# --------------------------------------------------------------------------
# Launch the application
# --------------------------------------------------------------------------
python3 main.py
