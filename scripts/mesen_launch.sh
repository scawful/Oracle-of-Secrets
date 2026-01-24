#!/usr/bin/env bash
# Launch Mesen2 with ROM and auto-load bridge script
# Supports yabai BSP mode for agent testing

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Defaults
MESEN_APP="${MESEN_APP:-}"
ROM_PATH="${ROM_PATH:-${REPO_ROOT}/Roms/oos168x.sfc}"
BRIDGE_KIND="live"
BRIDGE_SCRIPT="${REPO_ROOT}/scripts/mesen_live_bridge.lua"
MESEN2_DIR="${MESEN2_DIR:-}"
YABAI_MODE="${YABAI_MODE:-}" # Set to "bsp" or "float" for yabai control
INSTANCE_NAME="default"
ALLOW_MULTI=0

usage() {
    cat <<'EOF'
Launch Mesen2 with Oracle of Secrets ROM and bridge script

Usage: mesen_launch.sh [options]

Options:
  --rom PATH       ROM file to load (default: Roms/oos168x.sfc)
  --build          Rebuild ROM before launching
  --yabai MODE     Yabai window mode: bsp, float, background, space, or off (default: off)
  --yabai-space N  Send Mesen window to space N after launch (yabai)
  --set NAME       Apply a 10-slot save-state set before launch
  --instance NAME  Instance name (separate bridge dir)
  --multi          Do not close existing Mesen instances
  --bridge KIND    Bridge type: live or socket (default: live)
  --allow-stale    Allow ROM MD5 mismatch when applying a set
  --state N        Load save state slot N after launch (via bridge if available)
  --help           Show this help

Examples:
  mesen_launch.sh                    # Launch with defaults
  mesen_launch.sh --build            # Rebuild ROM first
  mesen_launch.sh --yabai bsp        # Use yabai BSP tiling
  mesen_launch.sh --state 1          # Load save state slot 1

Env:
  MESEN_APP    Override Mesen2 app bundle path
  MESEN2_DIR   Override Mesen2 data directory
EOF
}

BUILD=0
STATE_SLOT=""
SET_NAME=""
ALLOW_STALE=0
YABAI_SPACE=""

resolve_mesen_app() {
    if [[ -n "${MESEN_APP}" ]]; then
        echo "${MESEN_APP}"
        return
    fi

    local candidates=(
        "/Applications/Mesen2 OOS.app"
        "/Applications/Mesen.app"
        "/Users/scawful/src/third_party/forks/Mesen2/bin/osx-arm64/Release/osx-arm64/publish/Mesen2 OOS.app"
        "/Users/scawful/src/third_party/forks/Mesen2/bin/osx-arm64/Release/osx-arm64/publish/Mesen.app"
    )
    for path in "${candidates[@]}"; do
        if [[ -d "${path}" ]]; then
            echo "${path}"
            return
        fi
    done
    echo "/Applications/Mesen2 OOS.app"
}

resolve_mesen_dir() {
    if [[ -n "${MESEN2_DIR}" ]]; then
        echo "${MESEN2_DIR}"
        return
    fi

    local app_support="${HOME}/Library/Application Support/Mesen2"
    if [[ -d "${app_support}" ]]; then
        echo "${app_support}"
        return
    fi

    echo "${HOME}/Documents/Mesen2"
}

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
        --yabai-space)
            YABAI_SPACE="${2:-}"
            shift 2
            ;;
        --set)
            SET_NAME="${2:-}"
            shift 2
            ;;
        --allow-stale)
            ALLOW_STALE=1
            shift
            ;;
        --instance)
            INSTANCE_NAME="${2:-default}"
            shift 2
            ;;
        --bridge)
            BRIDGE_KIND="${2:-live}"
            shift 2
            ;;
        --multi)
            ALLOW_MULTI=1
            shift
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

case "${BRIDGE_KIND}" in
    live)
        BRIDGE_SCRIPT="${REPO_ROOT}/scripts/mesen_live_bridge.lua"
        ;;
    socket)
        BRIDGE_SCRIPT="${REPO_ROOT}/scripts/mesen_socket_bridge.lua"
        ;;
    *)
        echo "Unknown bridge type: ${BRIDGE_KIND}" >&2
        exit 1
        ;;
esac

MESEN_APP="$(resolve_mesen_app)"
MESEN2_DIR="$(resolve_mesen_dir)"

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

# Apply save-state set if requested
if [[ -n "${SET_NAME}" ]]; then
    echo "Applying save-state set: ${SET_NAME}"
    allow_flag=""
    if [[ "${ALLOW_STALE}" -eq 1 ]]; then
        allow_flag="--allow-stale"
    fi
    python3 "${REPO_ROOT}/scripts/state_library.py" set-apply \
        --set "${SET_NAME}" \
        --rom "${ROM_PATH}" \
        --force \
        ${allow_flag} || true
fi

# Setup directories
mkdir -p "${MESEN2_DIR}/Scripts" "${MESEN2_DIR}/bridge"

# Instance-specific bridge directory + script
BRIDGE_INSTANCE_DIR="${MESEN2_DIR}/bridge/${INSTANCE_NAME}"
mkdir -p "${BRIDGE_INSTANCE_DIR}"
BRIDGE_SCRIPT_NAME="mesen_live_bridge_${INSTANCE_NAME}.lua"
BRIDGE_SCRIPT_PATH="${MESEN2_DIR}/Scripts/${BRIDGE_SCRIPT_NAME}"
BRIDGE_CONFIG_PATH="${BRIDGE_SCRIPT_PATH}.json"
BRIDGE_GLOBAL_CONFIG="${MESEN2_DIR}/Scripts/bridge_config.json"
SCRIPT_DATA_DIR="${HOME}/Library/Application Support/Mesen2/LuaScriptData/mesen_live_bridge_${INSTANCE_NAME}"
SCRIPT_DATA_CONFIG="${SCRIPT_DATA_DIR}/bridge_config.json"

# Copy bridge script
cp "${BRIDGE_SCRIPT}" "${BRIDGE_SCRIPT_PATH}"
cat <<JSON > "${BRIDGE_CONFIG_PATH}"
{
  "bridge_dir": "${BRIDGE_INSTANCE_DIR}",
  "instance_id": "${INSTANCE_NAME}"
}
JSON
cat <<JSON > "${BRIDGE_GLOBAL_CONFIG}"
{
  "bridge_dir": "${BRIDGE_INSTANCE_DIR}",
  "instance_id": "${INSTANCE_NAME}"
}
JSON
mkdir -p "${SCRIPT_DATA_DIR}"
cat <<JSON > "${SCRIPT_DATA_CONFIG}"
{
  "bridge_dir": "${BRIDGE_INSTANCE_DIR}",
  "instance_id": "${INSTANCE_NAME}"
}
JSON
echo "Bridge script installed: ${BRIDGE_SCRIPT_PATH}"

# Gracefully quit existing Mesen2 instance
if [[ "${ALLOW_MULTI}" -eq 0 ]] && pgrep -q "Mesen"; then
    echo "Closing existing Mesen2..."
    # Use osascript for graceful quit on macOS
    osascript -e 'tell application "Mesen" to quit' 2>/dev/null || true
    # Wait for graceful shutdown
    for i in {1..10}; do
        if ! pgrep -q "Mesen"; then
            break
        fi
        sleep 0.3
    done
    # Force kill if still running
    if pgrep -q "Mesen"; then
        pkill -9 -f "Mesen" 2>/dev/null || true
    fi
    sleep 0.5
fi

# Configure yabai if requested
if [[ -n "${YABAI_MODE}" ]] && command -v yabai &>/dev/null; then
    "${REPO_ROOT}/scripts/yabai_mesen_rules.sh" apply "${YABAI_MODE}" "${YABAI_SPACE}" || true
    case "${YABAI_MODE}" in
        bsp) echo "Yabai: BSP tiling mode" ;;
        float) echo "Yabai: Floating mode (right side)" ;;
        background|below|bg) echo "Yabai: Background layer (floating, below)" ;;
        space) echo "Yabai: Space rule applied" ;;
        off) echo "Yabai: Disabled for Mesen" ;;
    esac
fi

# Launch Mesen2 with ROM and Lua script
# Mesen2 CLI: any .lua file passed as arg is auto-loaded and run
echo "Launching Mesen2 with: ${ROM_PATH}"
echo "Auto-loading script: ${BRIDGE_SCRIPT_PATH}"

# Use 'open' with --args for proper macOS argument passing
open -a "${MESEN_APP}" --args "${ROM_PATH}" "${BRIDGE_SCRIPT_PATH}"

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

if [[ "${BRIDGE_KIND}" == "live" ]]; then
    # Wait for bridge to become active (script is auto-loaded via CLI)
    echo -n "Waiting for bridge"
    BRIDGE_FILE="${BRIDGE_INSTANCE_DIR}/state.json"
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
        echo "  Script: ${BRIDGE_SCRIPT_PATH}"
    fi
else
    echo "Socket bridge loaded (state is pushed via TCP)."
    echo "Start hub: python3 scripts/mesen_socket_server.py"
fi

# Optional: move window behind or to a space after launch
if command -v yabai &>/dev/null; then
    if [[ -n "${YABAI_SPACE}" ]]; then
        sleep 0.5
        "${REPO_ROOT}/scripts/yabai_mesen_window.sh" stash "${YABAI_SPACE}" || true
    elif [[ "${YABAI_MODE}" == "background" || "${YABAI_MODE}" == "below" || "${YABAI_MODE}" == "bg" ]]; then
        sleep 0.5
        "${REPO_ROOT}/scripts/yabai_mesen_window.sh" hide || true
    elif [[ "${YABAI_MODE}" == "space" && -n "${SCRATCH_SPACE:-}" ]]; then
        sleep 0.5
        "${REPO_ROOT}/scripts/yabai_mesen_window.sh" stash "${SCRATCH_SPACE}" || true
    fi
fi

# Load save state if requested
if [[ -n "${STATE_SLOT}" ]]; then
    rom_base="$(basename "${ROM_PATH}" | sed 's/\.[^.]*$//')"
    state_path="${MESEN2_DIR}/SaveStates/${rom_base}_${STATE_SLOT}.mss"
    echo ""
    if [[ -f "${state_path}" ]]; then
        echo "Requesting savestate load: ${state_path}"
        "${REPO_ROOT}/scripts/mesen_cli.sh" loadstate "${state_path}" || true
        "${REPO_ROOT}/scripts/mesen_cli.sh" wait-load 10 || true
    else
        echo "Save state not found: ${state_path}"
        echo "Press F${STATE_SLOT} in Mesen2 to load slot ${STATE_SLOT} manually."
    fi
fi

echo ""
echo "Ready for testing. Use ./scripts/mesen_cli.sh to interact."
