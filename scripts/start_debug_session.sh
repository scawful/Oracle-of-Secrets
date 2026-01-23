#!/bin/bash
# Oracle of Secrets - Debug Session Launcher
#
# This script:
# 1. Starts Mesen2 with the ROM
# 2. Waits for Mesen2 to be ready
# 3. Opens the Script Window
# 4. Provides instructions for loading bridge scripts
#
# Usage: ./start_debug_session.sh [rom_path]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Default ROM
ROM_PATH="${1:-$PROJECT_DIR/Roms/oos91x.sfc}"

# Bridge scripts
MAIN_BRIDGE="$SCRIPT_DIR/mesen_live_bridge.lua"
DEBUG_BRIDGE="$SCRIPT_DIR/mesen_debug_bridge.lua"

# Find Mesen2
MESEN_APP="/Applications/Mesen.app"
if [[ ! -d "$MESEN_APP" ]]; then
    MESEN_APP="$HOME/Applications/Mesen.app"
fi
if [[ ! -d "$MESEN_APP" ]]; then
    MESEN_APP="$HOME/src/third_party/mesen2/bin/osx-arm64/Release/osx-arm64/publish/Mesen.app"
fi

if [[ ! -d "$MESEN_APP" ]]; then
    echo "Error: Mesen.app not found"
    exit 1
fi

if [[ ! -f "$ROM_PATH" ]]; then
    echo "Error: ROM not found: $ROM_PATH"
    exit 1
fi

echo "==================================="
echo " Oracle of Secrets Debug Session"
echo "==================================="
echo ""
echo "ROM:     $ROM_PATH"
echo "Mesen:   $MESEN_APP"
echo ""

# Create bridge directory
mkdir -p ~/Documents/Mesen2/bridge

# Launch Mesen2
echo "Starting Mesen2..."
open -a "$MESEN_APP" "$ROM_PATH" &

sleep 2

echo ""
echo "==================================="
echo " MANUAL STEPS REQUIRED"
echo "==================================="
echo ""
echo "1. In Mesen2, go to Debug > Script Window (or Cmd+Shift+S)"
echo ""
echo "2. Load the MAIN bridge:"
echo "   File > Open > $MAIN_BRIDGE"
echo "   Click 'Run'"
echo ""
echo "3. Load the DEBUG bridge (in a new tab):"
echo "   File > New Tab (Cmd+T)"
echo "   File > Open > $DEBUG_BRIDGE"
echo "   Click 'Run'"
echo ""
echo "4. Verify bridge connection:"
echo "   python3 $SCRIPT_DIR/mesen_cli.sh ping"
echo ""
echo "==================================="
echo ""

# Wait for bridge to be responsive
echo "Waiting for bridge connection..."
for i in {1..30}; do
    if "$SCRIPT_DIR/mesen_cli.sh" ping 2>/dev/null | grep -q "PONG"; then
        echo "Bridge connected!"
        exit 0
    fi
    sleep 1
    echo -n "."
done

echo ""
echo "Bridge not connected yet. Load the scripts manually."
