#!/usr/bin/env bash
# Launch Mesen2 with ROM and auto-load bridge script
# Supports yabai BSP mode for agent testing

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Defaults
MESEN_APP="${MESEN_APP:-/Users/scawful/src/third_party/mesen2/bin/osx-arm64/Release/osx-arm64/publish/Mesen.app}"
ROM_PATH="${ROM_PATH:-${REPO_ROOT}/Roms/oos168x.sfc}"
BRIDGE_SCRIPT="${REPO_ROOT}/scripts/mesen_live_bridge.lua"
MESEN2_DIR="${HOME}/Documents/Mesen2"
YABAI_MODE="${YABAI_MODE:-}" # Set to "bsp" or "float" for yabai control

usage() {
    cat <<'EOF'
Launch Mesen2 with Oracle of Secrets ROM and bridge script

Usage: mesen_launch.sh [options]

Options:
  --rom PATH       ROM file to load (default: Roms/oos168x.sfc)
  --build          Rebuild ROM before launching
  --yabai MODE     Yabai window mode: bsp, float, or off (default: off)
  --state N        Load save state slot N after launch
  --help           Show this help

Examples:
  mesen_launch.sh                    # Launch with defaults
  mesen_launch.sh --build            # Rebuild ROM first
  mesen_launch.sh --yabai bsp        # Use yabai BSP tiling
  mesen_launch.sh --state 1          # Load save state slot 1
EOF
}

BUILD=0
STATE_SLOT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rom)
            ROM_PATH="${2:-}"
            shift 2
            ;;
        --build)
            BUILD=1
            shift
            ;;
        --yabai)
            YABAI_MODE="${2:-}"
            shift 2
            ;;
        --state)
            STATE_SLOT="${2:-}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
    esac
done

# Rebuild ROM if requested
if [[ "${BUILD}" -eq 1 ]]; then
    echo "Building ROM..."
    "${SCRIPT_DIR}/build_rom.sh" 168
fi

# Verify ROM exists
if [[ ! -f "${ROM_PATH}" ]]; then
    echo "ROM not found: ${ROM_PATH}" >&2
    exit 1
fi

# Verify Mesen2 exists
if [[ ! -d "${MESEN_APP}" ]]; then
    echo "Mesen2 not found: ${MESEN_APP}" >&2
    exit 1
fi

# Setup directories
mkdir -p "${MESEN2_DIR}/Scripts" "${MESEN2_DIR}/bridge"

# Copy bridge script
cp "${BRIDGE_SCRIPT}" "${MESEN2_DIR}/Scripts/"
echo "Bridge script installed: ${MESEN2_DIR}/Scripts/mesen_live_bridge.lua"

# Kill existing Mesen2 instance
pkill -f "Mesen" 2>/dev/null || true
sleep 0.5

# Configure yabai if requested
if [[ -n "${YABAI_MODE}" ]] && command -v yabai &>/dev/null; then
    case "${YABAI_MODE}" in
        bsp)
            yabai -m rule --add app="Mesen" manage=on 2>/dev/null || true
            echo "Yabai: BSP tiling mode"
            ;;
        float)
            yabai -m rule --add app="Mesen" manage=off grid=6:6:4:0:2:3 2>/dev/null || true
            echo "Yabai: Floating mode (right side)"
            ;;
        off)
            yabai -m rule --remove app="Mesen" 2>/dev/null || true
            echo "Yabai: Disabled for Mesen"
            ;;
    esac
fi

# Launch Mesen2 with ROM and Lua script
# Mesen2 CLI: any .lua file passed as arg is auto-loaded and run
echo "Launching Mesen2 with: ${ROM_PATH}"
echo "Auto-loading script: ${BRIDGE_SCRIPT}"

# Use 'open' with --args for proper macOS argument passing
open -a "${MESEN_APP}" --args "${ROM_PATH}" "${BRIDGE_SCRIPT}"

# Wait for Mesen2 to start
echo -n "Waiting for Mesen2 to start"
for i in {1..30}; do
    if pgrep -q "Mesen"; then
        echo " OK"
        break
    fi
    echo -n "."
    sleep 0.2
done

if ! pgrep -q "Mesen"; then
    echo " FAILED"
    exit 1
fi

# Give Mesen2 time to initialize
sleep 1

# Wait for bridge to become active (script is auto-loaded via CLI)
echo -n "Waiting for bridge"
BRIDGE_FILE="${MESEN2_DIR}/bridge/state.json"
for i in {1..60}; do
    if [[ -f "${BRIDGE_FILE}" ]]; then
        # Check if file was modified recently (within 5 seconds)
        if [[ "$(uname)" == "Darwin" ]]; then
            age=$(($(date +%s) - $(stat -f %m "${BRIDGE_FILE}")))
        else
            age=$(($(date +%s) - $(stat -c %Y "${BRIDGE_FILE}")))
        fi
        if [[ $age -lt 5 ]]; then
            echo " OK"
            echo ""
            echo "=== Bridge Active ==="
            cat "${BRIDGE_FILE}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'Frame: {d[\"frame\"]}')
print(f'Mode: {d[\"mode\"]} Room: 0x{d[\"roomId\"]:02X}')
print(f'Link: ({d[\"linkX\"]}, {d[\"linkY\"]})')
" 2>/dev/null || cat "${BRIDGE_FILE}"
            break
        fi
    fi
    echo -n "."
    sleep 0.5
done

if [[ ! -f "${BRIDGE_FILE}" ]]; then
    echo ""
    echo "WARNING: Bridge not active. Check Mesen2 console for script errors."
    echo "  Script: ${BRIDGE_SCRIPT}"
fi

# Load save state if requested
if [[ -n "${STATE_SLOT}" ]]; then
    echo ""
    echo "Note: Save state loading requires manual action in Mesen2"
    echo "Press F${STATE_SLOT} to load slot ${STATE_SLOT}"
fi

echo ""
echo "Ready for testing. Use ./scripts/mesen_cli.sh to interact."
