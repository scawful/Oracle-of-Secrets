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

# Default ROM (patched)
ROM_PATH="${1:-$PROJECT_DIR/Roms/oos168x.sfc}"

# Watch preset to auto-load after bridge connects (debug bridge required).
# Use WATCH_PRESET=none to disable. WATCH_CLEAR=1 clears existing watches first.
WATCH_PRESET="${WATCH_PRESET:-${2:-debug}}"
WATCH_CLEAR="${WATCH_CLEAR:-0}"

# Find Mesen2 OOS fork
MESEN_APP="/Applications/Mesen2 OOS.app"
if [[ ! -d "$MESEN_APP" ]]; then
    MESEN_APP="$HOME/src/hobby/mesen2-oos/bin/osx-arm64/Release/osx-arm64/publish/Mesen2 OOS.app"
fi

resolve_rom_path() {
    local input="$1"
    if [[ -z "${input}" ]]; then
        echo ""
        return
    fi
    if [[ "${input}" == "~/"* ]]; then
        input="${HOME}/${input#~/}"
    fi
    if [[ "${input}" != /* ]]; then
        if [[ -e "${input}" ]]; then
            input="$(cd "$(dirname "${input}")" && pwd -P)/$(basename "${input}")"
        elif [[ -e "${PROJECT_DIR}/${input}" ]]; then
            input="$(cd "${PROJECT_DIR}/$(dirname "${input}")" && pwd -P)/$(basename "${input}")"
        fi
    fi
    if [[ -d "${input}" ]]; then
        local found
        found=$(ls "${input}"/oos*x.sfc 2>/dev/null | grep -E 'x\\.sfc$' | sort -V | tail -n 1 || true)
        if [[ -n "${found}" ]]; then
            echo "${found}"
            return
        fi
        found=$(ls "${input}"/*.sfc "${input}"/*.smc 2>/dev/null | head -n 1 || true)
        if [[ -n "${found}" ]]; then
            echo "${found}"
            return
        fi
    fi
    echo "${input}"
}

ROM_PATH="$(resolve_rom_path "${ROM_PATH}")"

if [[ ! -d "$MESEN_APP" ]]; then
    echo "Error: Mesen2 OOS.app not found"
    exit 1
fi

if [[ ! -f "$ROM_PATH" ]]; then
    echo "Error: ROM not found: $ROM_PATH"
    echo "Tip: pass a directory (it will search for the latest oos*x.sfc patched ROM)." >&2
    exit 1
fi

ROM_BASE="$(basename "${ROM_PATH}" | sed 's/\.[^.]*$//')"
if [[ "${ROM_BASE}" == *test* || "${ROM_BASE}" == "oos91x" || "${ROM_BASE}" =~ ^oos[0-9]+$ ]]; then
    echo "Error: refusing to launch editing ROM in Mesen2: ${ROM_PATH}" >&2
    echo "Use the patched ROM (e.g., Roms/oos168x.sfc)." >&2
    exit 1
fi

echo "==================================="
echo " Oracle of Secrets Debug Session"
echo "==================================="
echo ""
echo "ROM:     $ROM_PATH"
echo "Mesen:   $MESEN_APP"
echo ""

# Launch Mesen2
echo "Starting Mesen2..."
open -a "$MESEN_APP" "$ROM_PATH" &

sleep 2

echo ""
echo "==================================="
echo " SESSION READY"
echo "==================================="
echo ""
echo "Mesen2-OoS Socket API is active."
echo "Use 'python3 scripts/mesen2_client.py' for interaction."
echo ""
echo "Verify connection:"
echo "   python3 $SCRIPT_DIR/mesen2_client.py health"
echo ""
echo "==================================="
echo ""

# Wait for bridge to be responsive
echo "Waiting for socket connection..."
for i in {1..30}; do
    if python3 "$SCRIPT_DIR/mesen2_client.py" health 2>/dev/null | grep -q "UP"; then
        echo "Socket connected!"
        if [[ "${WATCH_PRESET}" != "none" ]]; then
            echo "Loading watch preset: ${WATCH_PRESET}"
            if [[ "${WATCH_CLEAR}" == "1" ]]; then
                if ! python3 "$SCRIPT_DIR/mesen2_client.py" watch-load --preset "${WATCH_PRESET}" --clear; then
                    echo "Watch preset load failed."
                fi
            else
                if ! python3 "$SCRIPT_DIR/mesen2_client.py" watch-load --preset "${WATCH_PRESET}"; then
                    echo "Watch preset load failed."
                fi
            fi
        fi
        exit 0
    fi
    sleep 1
    echo -n "."
done

echo ""
echo "Socket server not responding. Ensure Mesen2-OoS is running with Socket API enabled."
