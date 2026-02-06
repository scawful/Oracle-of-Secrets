#!/usr/bin/env bash
# Launch Mesen2 with ROM and auto-load bridge script
# Supports yabai BSP mode for agent testing

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Defaults
MESEN_APP="${MESEN_APP:-}"
ROM_PATH="${ROM_PATH:-}"
ROM_DEFAULT_PATCHED="${REPO_ROOT}/Roms/oos168x.sfc"
BRIDGE_KIND="live"
BRIDGE_SCRIPT="${REPO_ROOT}/scripts/mesen_live_bridge.lua"
MESEN2_DIR="${MESEN2_DIR:-}"
YABAI_MODE="${YABAI_MODE:-}" # Set to "bsp" or "float" for yabai control
INSTANCE_NAME="default"
ALLOW_MULTI=0
INSTANCE_SPECIFIED=0
AUTO_INSTANCE=0
OWNER=""
SCALE_ON_LAUNCH=""
SCALE_DELAY="0.4"
LAUNCH_PID=""
LAUNCH_SOCKET=""
HOME_OVERRIDE=""
INSTANCE_GUID=""
AGENT_TITLE=""  # Agent window title suffix (e.g., "Claude: Debug Task")
HIDE_AFTER_LAUNCH=0  # Set to 1 via --hide-after to hide window after launch
MINIMIZE_SCRIPT_WINDOW=1
MINIMIZE_DEBUG_WINDOWS=1
MINIMIZE_TITLES_DEFAULT="Script Window|Debugger|State Inspector"
MINIMIZE_TITLES=""
DEBUG_DEFAULTS=0
DEBUG_DEFAULTS_SPECIFIED=0
OPEN_DEBUGGER=0
OPEN_STATE_INSPECTOR=0
ENABLE_WATCH_HUD=0
AUTO_DEBUG=0
SOCKETS_BEFORE=()
EXPORT_ENV=0

usage() {
    cat <<'EOF'
Launch Mesen2 with Oracle of Secrets ROM and bridge script

Usage: mesen_launch.sh [options]

Options:
  --rom PATH       ROM file to load (default: Roms/oos168x.sfc)
  --app PATH       Mesen2 .app bundle path (overrides MESEN_APP)
  --build          Rebuild ROM before launching
  --yabai MODE     Yabai window mode: bsp, float, background, space, or off (default: off)
  --yabai-space N  Send Mesen window to space N after launch (yabai)
  --set NAME       Apply a 10-slot save-state set before launch
  --instance NAME  Instance name (separate bridge dir)
  --owner NAME     Owner/agent name for registry (optional)
  --multi          Do not close existing Mesen instances
  --bridge KIND    Bridge type: live or socket (default: live)
  --allow-stale    Allow ROM MD5 mismatch when applying a set
  --state N        Load save state slot N after launch (via bridge if available)
  --scale N        Apply window scale (1-10) using Mesen2 shortcut (Option/Alt+N)
  --scale-delay S  Delay before applying scale hotkey (default: 0.4)
  --home PATH      Override MESEN2_HOME for this instance
  --instance-guid GUID  Override MESEN2_INSTANCE_GUID for this instance
  --title TEXT     Set agent window title suffix (e.g., "Claude: Debug Task")
  --hide-after     Hide window (yabai layer=below) after launch
  --keep-script-window  Do not auto-minimize the Script Window after launch
  --keep-debug-windows  Do not auto-minimize Debugger/Inspector windows after launch
  --minimize-titles LIST  Override window titles to minimize (pipe-separated)
  --debugger       Open the Debugger window on launch
  --state-inspector  Open the State Inspector on launch
  --watch-hud      Enable the Watch HUD on launch
  --auto-debug     Enable debugger + inspector + watch HUD
  --debug-defaults Enable Watch HUD + State Inspector on launch
  --no-debug-defaults Disable default debug windows/HUD (default)
  --export-env     Print export lines for MESEN2_INSTANCE/MESEN2_SOCKET_PATH
  --help           Show this help

Examples:
  mesen_launch.sh                    # Launch patched ROM (default)
  mesen_launch.sh --build            # Rebuild ROM first
  mesen_launch.sh --yabai bsp        # Use yabai BSP tiling
  mesen_launch.sh --state 1          # Load save state slot 1

Env:
  MESEN_APP    Override Mesen2 app bundle path
  MESEN2_DIR   Override Mesen2 data directory
  MESEN_DEBUG_DEFAULTS  Set to 1 to enable default debug HUD + inspector
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
        "/Users/scawful/src/hobby/mesen2-oos/bin/osx-arm64/Release/osx-arm64/publish/Mesen2 OOS.app"
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

    local docs="${HOME}/Documents/Mesen2"
    if [[ -d "${docs}" ]]; then
        echo "${docs}"
        return
    fi

    local app_support="${HOME}/Library/Application Support/Mesen2"
    if [[ -d "${app_support}" ]]; then
        echo "${app_support}"
        return
    fi

    local xdg_config="${HOME}/.config/mesen2"
    if [[ -d "${xdg_config}" ]]; then
        echo "${xdg_config}"
        return
    fi
    local xdg_config_caps="${HOME}/.config/Mesen2"
    if [[ -d "${xdg_config_caps}" ]]; then
        echo "${xdg_config_caps}"
        return
    fi

    echo "${HOME}/Documents/Mesen2"
}

resolve_mesen_bin() {
    local bin_path="${MESEN_APP}/Contents/MacOS/Mesen"
    if [[ -x "${bin_path}" ]]; then
        echo "${bin_path}"
        return
    fi
    echo "${bin_path}"
}

resolve_rom_path() {
    local input="$1"
    if [[ -z "${input}" ]]; then
        echo ""
        return
    fi

    # Expand ~ to $HOME
    if [[ "${input}" == "~/"* ]]; then
        input="${HOME}/${input#~/}"
    fi

    # Resolve relative paths against cwd and repo root
    if [[ "${input}" != /* ]]; then
        if [[ -e "${input}" ]]; then
            input="$(cd "$(dirname "${input}")" && pwd -P)/$(basename "${input}")"
        elif [[ -e "${REPO_ROOT}/${input}" ]]; then
            input="$(cd "${REPO_ROOT}/$(dirname "${input}")" && pwd -P)/$(basename "${input}")"
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

seed_mesen_home() {
    local dest="$1"
    local src="$2"

    if [[ -z "${dest}" || -z "${src}" ]]; then
        return 0
    fi
    if [[ "${dest}" == "${src}" ]]; then
        return 0
    fi
    if [[ ! -d "${src}" ]]; then
        return 0
    fi

    local files=(MesenCore.dylib MesenNesDB.txt libSkiaSharp.dylib libHarfBuzzSharp.dylib settings.json)
    for file in "${files[@]}"; do
        if [[ ! -e "${dest}/${file}" && -e "${src}/${file}" ]]; then
            cp "${src}/${file}" "${dest}/${file}" 2>/dev/null || true
        fi
    done
    if [[ -d "${src}/Satellaview" && ! -d "${dest}/Satellaview" ]]; then
        cp -R "${src}/Satellaview" "${dest}/Satellaview" 2>/dev/null || true
    fi
    if [[ -d "${src}/GameConfig" && ! -d "${dest}/GameConfig" ]]; then
        cp -R "${src}/GameConfig" "${dest}/GameConfig" 2>/dev/null || true
    fi
}

apply_scale_hotkey() {
    local scale="$1"
    local app_name key

    if [[ -z "${scale}" ]]; then
        return 0
    fi
    if ! [[ "${scale}" =~ ^[0-9]+$ ]]; then
        echo "Invalid scale value: ${scale}" >&2
        return 1
    fi
    if (( scale < 1 || scale > 10 )); then
        echo "Scale must be between 1 and 10 (got ${scale})." >&2
        return 1
    fi

    key="${scale}"
    if [[ "${scale}" -eq 10 ]]; then
        key="0"
    fi

    if ! command -v osascript &>/dev/null; then
        echo "osascript not available; press Option/Alt+${key} in Mesen2 to set scale." >&2
        return 0
    fi

    app_name="$(basename "${MESEN_APP}" .app)"
    osascript -e "tell application \"${app_name}\" to activate" >/dev/null 2>&1 || true
    osascript -e "tell application \"System Events\" to keystroke \"${key}\" using {option down}" >/dev/null 2>&1 || true
}

activate_mesen_app() {
    local app_name

    if ! command -v osascript &>/dev/null; then
        return 0
    fi

    app_name="$(basename "${MESEN_APP}" .app)"
    osascript -e "tell application \"${app_name}\" to activate" >/dev/null 2>&1 || true
}

minimize_script_window() {
    local app_name

    if ! command -v osascript &>/dev/null; then
        return 0
    fi

    app_name="$(basename "${MESEN_APP}" .app)"
    osascript <<APPLESCRIPT >/dev/null 2>&1 || true
tell application "System Events"
    if exists process "${app_name}" then
        tell process "${app_name}"
            repeat with w in windows
                if (name of w) contains "Script Window" then
                    try
                        set minimized of w to true
                    end try
                end if
            end repeat
        end tell
    end if
end tell
APPLESCRIPT
}

minimize_window_by_title() {
    local title="$1"
    local app_name

    if ! command -v osascript &>/dev/null; then
        return 0
    fi

    app_name="$(basename "${MESEN_APP}" .app)"
    osascript <<APPLESCRIPT >/dev/null 2>&1 || true
tell application "System Events"
    if exists process "${app_name}" then
        tell process "${app_name}"
            repeat with w in windows
                try
                    set wname to name of w
                on error
                    set wname to ""
                end try
                if wname contains "${title}" then
                    try
                        set minimized of w to true
                    end try
                    try
                        click (first button whose subrole is "AXMinimizeButton") of w
                    end try
                end if
            end repeat
        end tell
    end if
end tell
APPLESCRIPT
}

minimize_debug_windows() {
    local title_list="${MINIMIZE_TITLES:-${MESEN_MINIMIZE_TITLES:-${MINIMIZE_TITLES_DEFAULT}}}"
    local title
    local IFS="|"
    read -r -a titles <<< "${title_list}"
    for title in "${titles[@]}"; do
        if [[ -n "${title}" ]]; then
            minimize_window_by_title "${title}"
        fi
    done
    if command -v yabai &>/dev/null; then
        TITLE_REGEX="${title_list}" "${REPO_ROOT}/scripts/yabai_mesen_window.sh" minimize || true
    fi
}

list_mesen_sockets() {
    local sockets=()
    shopt -s nullglob
    sockets=(/tmp/mesen2-*.sock)
    shopt -u nullglob
    if [[ ${#sockets[@]} -eq 0 ]]; then
        return 0
    fi
    ls -t "${sockets[@]}" 2>/dev/null || printf '%s\n' "${sockets[@]}"
}

detect_new_socket() {
    local sock pre found
    mapfile -t SOCKETS_AFTER < <(list_mesen_sockets)
    for sock in "${SOCKETS_AFTER[@]}"; do
        found=0
        for pre in "${SOCKETS_BEFORE[@]}"; do
            if [[ "${sock}" == "${pre}" ]]; then
                found=1
                break
            fi
        done
        if [[ "${found}" -eq 0 ]]; then
            echo "${sock}"
            return 0
        fi
    done
    return 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rom)
            ROM_PATH="${2:-}"
            shift 2
            ;;
        --app|--mesen-app)
            MESEN_APP="${2:-}"
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
            INSTANCE_SPECIFIED=1
            shift 2
            ;;
        --owner)
            OWNER="${2:-}"
            shift 2
            ;;
        --bridge)
            BRIDGE_KIND="${2:-live}"
            shift 2
            ;;
        --scale)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --scale requires a number" >&2
                exit 1
            fi
            if ! [[ "$2" =~ ^[0-9]+$ ]]; then
                echo "Error: --scale must be an integer" >&2
                exit 1
            fi
            SCALE_ON_LAUNCH="$2"
            shift 2
            ;;
        --scale-delay)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --scale-delay requires a number" >&2
                exit 1
            fi
            if ! [[ "$2" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
                echo "Error: --scale-delay must be a number" >&2
                exit 1
            fi
            SCALE_DELAY="$2"
            shift 2
            ;;
        --home)
            HOME_OVERRIDE="${2:-}"
            shift 2
            ;;
        --instance-guid)
            INSTANCE_GUID="${2:-}"
            shift 2
            ;;
        --title)
            AGENT_TITLE="${2:-}"
            shift 2
            ;;
        --hide-after)
            HIDE_AFTER_LAUNCH=1
            shift
            ;;
        --keep-script-window)
            MINIMIZE_SCRIPT_WINDOW=0
            shift
            ;;
        --keep-debug-windows)
            MINIMIZE_DEBUG_WINDOWS=0
            shift
            ;;
        --minimize-titles)
            MINIMIZE_TITLES="${2:-}"
            shift 2
            ;;
        --debugger)
            OPEN_DEBUGGER=1
            shift
            ;;
        --state-inspector)
            OPEN_STATE_INSPECTOR=1
            shift
            ;;
        --watch-hud)
            ENABLE_WATCH_HUD=1
            shift
            ;;
        --auto-debug)
            AUTO_DEBUG=1
            shift
            ;;
        --debug-defaults)
            DEBUG_DEFAULTS=1
            DEBUG_DEFAULTS_SPECIFIED=1
            shift
            ;;
        --no-debug-defaults)
            DEBUG_DEFAULTS=0
            DEBUG_DEFAULTS_SPECIFIED=1
            shift
            ;;
        --multi)
            ALLOW_MULTI=1
            shift
            ;;
        --export-env)
            EXPORT_ENV=1
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

if [[ -n "${MESEN_DEBUG_DEFAULTS:-}" && "${DEBUG_DEFAULTS_SPECIFIED}" -eq 0 ]]; then
    debug_defaults_val="$(printf '%s' "${MESEN_DEBUG_DEFAULTS}" | tr '[:upper:]' '[:lower:]')"
    case "${debug_defaults_val}" in
        0|false|no|off) DEBUG_DEFAULTS=0 ;;
        1|true|yes|on) DEBUG_DEFAULTS=1 ;;
    esac
fi

if [[ "${AUTO_DEBUG}" -eq 1 ]]; then
    OPEN_DEBUGGER=1
    OPEN_STATE_INSPECTOR=1
    ENABLE_WATCH_HUD=1
elif [[ "${DEBUG_DEFAULTS}" -eq 1 ]]; then
    OPEN_DEBUGGER=1
    OPEN_STATE_INSPECTOR=1
    ENABLE_WATCH_HUD=1
fi

if [[ "${INSTANCE_SPECIFIED}" -eq 1 && "${INSTANCE_NAME}" != "default" && "${ALLOW_MULTI}" -eq 0 ]]; then
    ALLOW_MULTI=1
fi

if [[ "${ALLOW_MULTI}" -eq 1 && "${INSTANCE_NAME}" == "default" ]]; then
    if [[ "${INSTANCE_SPECIFIED}" -eq 0 ]]; then
        INSTANCE_NAME="multi-$(date +%Y%m%d_%H%M%S)-$$"
        AUTO_INSTANCE=1
    else
        echo "Warning: --multi with instance 'default' will reuse bridge dir; consider --instance <name>." >&2
    fi
fi

if [[ -z "${ROM_PATH}" ]]; then
    ROM_PATH="${ROM_DEFAULT_PATCHED}"
fi
ROM_PATH="$(resolve_rom_path "${ROM_PATH}")"
if [[ -z "${ROM_PATH}" ]]; then
    echo "ROM path is empty after resolution." >&2
    exit 1
fi
ROM_BASE="$(basename "${ROM_PATH}" | sed 's/\.[^.]*$//')"
if [[ "${ROM_BASE}" == *test* || "${ROM_BASE}" == "oos91x" || "${ROM_BASE}" =~ ^oos[0-9]+$ ]]; then
    echo "Refusing to launch editing ROM: ${ROM_PATH}" >&2
    echo "Use the patched ROM (e.g., Roms/oos168x.sfc) for Mesen2." >&2
    exit 1
fi

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

if [[ -n "${SCALE_ON_LAUNCH}" ]]; then
    if (( SCALE_ON_LAUNCH < 1 || SCALE_ON_LAUNCH > 10 )); then
        echo "Error: --scale must be between 1 and 10" >&2
        exit 1
    fi
fi

if [[ -z "${HOME_OVERRIDE}" && "${ALLOW_MULTI}" -eq 1 && "${INSTANCE_NAME}" != "default" ]]; then
    HOME_OVERRIDE="${HOME}/.config/mesen2-${INSTANCE_NAME}"
fi

if [[ -n "${HOME_OVERRIDE}" ]]; then
    mkdir -p "${HOME_OVERRIDE}"
fi

if [[ -z "${INSTANCE_GUID}" && "${ALLOW_MULTI}" -eq 1 && "${INSTANCE_NAME}" != "default" ]]; then
    GUID_FILE="${HOME_OVERRIDE}/instance_guid.txt"
    if [[ -f "${GUID_FILE}" ]]; then
        INSTANCE_GUID="$(cat "${GUID_FILE}")"
    else
        if command -v uuidgen >/dev/null 2>&1; then
            INSTANCE_GUID="$(uuidgen)"
        else
            INSTANCE_GUID="$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)"
        fi
        echo "${INSTANCE_GUID}" > "${GUID_FILE}"
    fi
fi

if [[ -n "${INSTANCE_GUID}" ]]; then
    if ! [[ "${INSTANCE_GUID}" =~ ^[A-Fa-f0-9-]+$ ]]; then
        echo "Error: --instance-guid must be a GUID string" >&2
        exit 1
    fi
fi

MESEN_APP="$(resolve_mesen_app)"
MESEN2_DIR_BASE="$(resolve_mesen_dir)"

if [[ -z "${MESEN2_DIR}" ]]; then
    if [[ -n "${HOME_OVERRIDE}" ]]; then
        MESEN2_DIR="${HOME_OVERRIDE}"
    else
        MESEN2_DIR="${MESEN2_DIR_BASE}"
    fi
fi

if [[ -n "${HOME_OVERRIDE}" ]]; then
    seed_mesen_home "${HOME_OVERRIDE}" "${MESEN2_DIR_BASE}"
fi

# Rebuild ROM if requested
if [[ "${BUILD}" -eq 1 ]]; then
    echo "Building ROM..."
    "${SCRIPT_DIR}/build_rom.sh" 168
fi

# Verify ROM exists
if [[ ! -f "${ROM_PATH}" ]]; then
    echo "ROM not found: ${ROM_PATH}" >&2
    echo "Tip: --rom can be a directory; it will search for the latest oos*x.sfc patched ROM." >&2
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
        --mesen-dir "${MESEN2_DIR}/SaveStates" \
        --mesen-saves-dir "${MESEN2_DIR}/Saves" \
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
SCRIPT_DATA_DIR="${MESEN2_DIR}/LuaScriptData/mesen_live_bridge_${INSTANCE_NAME}"
SCRIPT_DATA_CONFIG="${SCRIPT_DATA_DIR}/bridge_config.json"

# Copy bridge script
cp "${BRIDGE_SCRIPT}" "${BRIDGE_SCRIPT_PATH}"
cat <<JSON > "${BRIDGE_CONFIG_PATH}"
{
  "bridge_dir": "${BRIDGE_INSTANCE_DIR}",
  "instance_id": "${INSTANCE_NAME}",
  "rom_base": "${ROM_BASE}"
}
JSON
cat <<JSON > "${BRIDGE_GLOBAL_CONFIG}"
{
  "bridge_dir": "${BRIDGE_INSTANCE_DIR}",
  "instance_id": "${INSTANCE_NAME}",
  "rom_base": "${ROM_BASE}"
}
JSON
mkdir -p "${SCRIPT_DATA_DIR}"
cat <<JSON > "${SCRIPT_DATA_CONFIG}"
{
  "bridge_dir": "${BRIDGE_INSTANCE_DIR}",
  "instance_id": "${INSTANCE_NAME}",
  "rom_base": "${ROM_BASE}"
}
JSON
echo "Bridge script installed: ${BRIDGE_SCRIPT_PATH}"

# Gracefully quit existing Mesen2 instance
if [[ "${ALLOW_MULTI}" -eq 0 ]] && pgrep -q "Mesen"; then
    echo "Closing existing Mesen2..."
    # Determine app name from MESEN_APP
    resolved_app="$(resolve_mesen_app)"
    app_name="$(basename "${resolved_app}" .app)"
    # Use osascript for graceful quit on macOS (avoids crash reporter)
    osascript -e "tell application \"${app_name}\" to quit" 2>/dev/null || true
    # Wait for graceful shutdown
    for i in {1..15}; do
        if ! pgrep -q "Mesen"; then
            break
        fi
        sleep 0.3
    done
    # Send SIGTERM if still running (gentler than SIGKILL)
    if pgrep -q "Mesen"; then
        pkill -TERM -f "Mesen" 2>/dev/null || true
        sleep 1
    fi
    # Only force kill as last resort
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
EXTRA_ARGS=()
if [[ "${AUTO_DEBUG}" -eq 1 ]]; then
    EXTRA_ARGS+=(--autoDebug)
else
    if [[ "${OPEN_DEBUGGER}" -eq 1 ]]; then
        EXTRA_ARGS+=(--openDebugger)
    fi
    if [[ "${OPEN_STATE_INSPECTOR}" -eq 1 ]]; then
        EXTRA_ARGS+=(--openStateInspector)
    fi
    if [[ "${ENABLE_WATCH_HUD}" -eq 1 ]]; then
        EXTRA_ARGS+=(--enableWatchHud)
    fi
fi

echo "Launching Mesen2 with: ${ROM_PATH}"
echo "Auto-loading script: ${BRIDGE_SCRIPT_PATH}"
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    echo "Debug flags: ${EXTRA_ARGS[*]}"
fi

if [[ "${AUTO_INSTANCE}" -eq 1 ]]; then
    echo "Auto instance name: ${INSTANCE_NAME}"
fi

if [[ "${ALLOW_MULTI}" -eq 1 ]]; then
    mapfile -t SOCKETS_BEFORE < <(list_mesen_sockets)
fi

# Use 'open' with --args for proper macOS argument passing (single instance).
# For multi-instance or when env vars are required (title/home/guid), launch the binary directly.
LAUNCH_DIRECT=0
if [[ "${ALLOW_MULTI}" -eq 1 || -n "${HOME_OVERRIDE}" || -n "${INSTANCE_GUID}" || -n "${AGENT_TITLE}" ]]; then
    LAUNCH_DIRECT=1
fi

if [[ "${LAUNCH_DIRECT}" -eq 1 ]]; then
    MESEN_BIN="$(resolve_mesen_bin)"
    if [[ ! -x "${MESEN_BIN}" ]]; then
        echo "Mesen2 binary not found: ${MESEN_BIN}" >&2
        exit 1
    fi
    MESEN_ENV=()
    if [[ -n "${HOME_OVERRIDE}" ]]; then
        MESEN_ENV+=(MESEN2_HOME="${HOME_OVERRIDE}")
    fi
    if [[ -n "${INSTANCE_GUID}" ]]; then
        MESEN_ENV+=(MESEN2_INSTANCE_GUID="${INSTANCE_GUID}")
    fi
    if [[ -n "${AGENT_TITLE}" ]]; then
        MESEN_ENV+=(MESEN2_AGENT_TITLE="${AGENT_TITLE}")
    fi
    env "${MESEN_ENV[@]}" "${MESEN_BIN}" "${EXTRA_ARGS[@]}" "${ROM_PATH}" "${BRIDGE_SCRIPT_PATH}" >/tmp/mesen2-${INSTANCE_NAME}.log 2>&1 &
    LAUNCH_PID=$!
    if [[ "${ALLOW_MULTI}" -eq 1 ]]; then
        LAUNCH_SOCKET="/tmp/mesen2-${LAUNCH_PID}.sock"
    fi
else
    open -a "${MESEN_APP}" --args "${EXTRA_ARGS[@]}" "${ROM_PATH}" "${BRIDGE_SCRIPT_PATH}"
fi

# Wait for Mesen2 to start
echo -n "Waiting for Mesen2 to start"
if [[ -n "${LAUNCH_PID}" ]]; then
    for i in {1..30}; do
        if kill -0 "${LAUNCH_PID}" 2>/dev/null; then
            echo " OK"
            break
        fi
        echo -n "."
        sleep 0.2
    done
else
    for i in {1..30}; do
        if pgrep -q "Mesen"; then
            echo " OK"
            break
        fi
        echo -n "."
        sleep 0.2
    done
fi

if [[ -n "${LAUNCH_PID}" ]]; then
    if ! kill -0 "${LAUNCH_PID}" 2>/dev/null; then
        echo " FAILED"
        exit 1
    fi
elif ! pgrep -q "Mesen"; then
    echo " FAILED"
    exit 1
fi

# Give Mesen2 time to initialize
sleep 1

if [[ "${HIDE_AFTER_LAUNCH}" -eq 0 ]]; then
    case "${YABAI_MODE}" in
        background|below|bg) ;;
        *) activate_mesen_app ;;
    esac
fi

if [[ "${MINIMIZE_SCRIPT_WINDOW}" -eq 1 ]]; then
    sleep 0.4
    minimize_script_window
fi

if [[ "${MINIMIZE_DEBUG_WINDOWS}" -eq 1 ]]; then
    sleep 0.2
    minimize_debug_windows
fi

if [[ "${ALLOW_MULTI}" -eq 1 ]]; then
    if [[ -n "${LAUNCH_PID}" ]]; then
        LAUNCH_SOCKET="/tmp/mesen2-${LAUNCH_PID}.sock"
        if [[ ! -S "${LAUNCH_SOCKET}" ]]; then
            LAUNCH_SOCKET=""
        fi
    fi
    for i in {1..30}; do
        if [[ -n "${LAUNCH_SOCKET}" && -S "${LAUNCH_SOCKET}" ]]; then
            break
        fi
        new_socket="$(detect_new_socket 2>/dev/null || true)"
        if [[ -n "${new_socket}" ]]; then
            LAUNCH_SOCKET="${new_socket}"
            break
        fi
        sleep 0.2
    done
fi

if [[ -n "${SCALE_ON_LAUNCH}" ]]; then
    sleep "${SCALE_DELAY}"
    apply_scale_hotkey "${SCALE_ON_LAUNCH}" || true
fi

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
                python3 -c 'import json,sys; d=json.load(sys.stdin); print("Frame:", d["frame"]); print("Mode: %s Room: 0x%02X" % (d["mode"], d["roomId"])); print("Link: (%s, %s)" % (d["linkX"], d["linkY"]))' \
                    2>/dev/null < "${BRIDGE_FILE}" || cat "${BRIDGE_FILE}"
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

# Optional: register instance ownership for multi-agent coordination
if [[ -n "${OWNER}" ]]; then
    if [[ -f "${REPO_ROOT}/scripts/mesen2_registry.py" ]]; then
        claim_args=(claim --instance "${INSTANCE_NAME}" --owner "${OWNER}" --rom "${ROM_PATH}" --bridge "${BRIDGE_KIND}")
        if [[ -n "${LAUNCH_SOCKET}" ]]; then
            claim_args+=(--socket "${LAUNCH_SOCKET}")
        elif [[ -n "${LAUNCH_PID}" ]]; then
            claim_args+=(--pid "${LAUNCH_PID}")
        fi
        python3 "${REPO_ROOT}/scripts/mesen2_registry.py" "${claim_args[@]}" || true
    fi
fi

if [[ "${EXPORT_ENV}" -eq 1 ]]; then
    if [[ -n "${LAUNCH_SOCKET}" ]]; then
        echo "export MESEN2_INSTANCE=${INSTANCE_NAME}"
        echo "export MESEN2_SOCKET_PATH=${LAUNCH_SOCKET}"
    elif [[ -f "${REPO_ROOT}/scripts/mesen2_registry.py" ]]; then
        python3 "${REPO_ROOT}/scripts/mesen2_registry.py" resolve --instance "${INSTANCE_NAME}" --export || true
    else
        echo "NOTE: socket not detected; set MESEN2_SOCKET_PATH manually." >&2
    fi
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
    elif [[ "${HIDE_AFTER_LAUNCH}" -eq 1 ]]; then
        sleep 0.5
        "${REPO_ROOT}/scripts/yabai_mesen_window.sh" hide || true
    fi
fi

# Load save state if requested
if [[ -n "${STATE_SLOT}" ]]; then
    state_path="${MESEN2_DIR}/SaveStates/${ROM_BASE}_${STATE_SLOT}.mss"
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
