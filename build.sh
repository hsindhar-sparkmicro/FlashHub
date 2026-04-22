#!/bin/bash
# Build script for Linux

set -e

echo "=== Building FlashHub for Linux ==="

# Activate virtual environment if it exists
if [ -d "vnev" ]; then
    source vnev/bin/activate
fi

# Install PyInstaller if not present
pip install pyinstaller

# Clean previous builds
rm -rf build dist

# Build with spec file
pyinstaller FlashHub.spec

echo ""
echo "=== Build Complete ==="
echo "Executable created: dist/FlashHub"
echo "Install launcher with: ./install_launcher.sh"
echo ""
echo "To test: ./dist/FlashHub"
