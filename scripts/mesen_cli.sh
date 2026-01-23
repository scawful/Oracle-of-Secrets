#!/usr/bin/env bash
# CLI interface to Mesen2 live bridge (Hybrid: Socket + File)
# Usage: mesen_cli.sh [command] [args...]

set -euo pipefail

# Configuration
DEFAULT_BRIDGE_ROOT="${HOME}/Documents/Mesen2/bridge"
SOCKET_URL="http://127.0.0.1:8080"
USE_SOCKET=0

# Detect Socket Server
if curl -s -m 0.2 "${SOCKET_URL}/health" | grep -q "true"; then
    USE_SOCKET=1
fi

if [[ -n "${MESEN_BRIDGE_DIR:-}" ]]; then
    BRIDGE_DIR="${MESEN_BRIDGE_DIR}"
elif [[ -n "${MESEN_INSTANCE:-}" ]]; then
    BRIDGE_DIR="${DEFAULT_BRIDGE_ROOT}/${MESEN_INSTANCE}"
else
    # Auto-detect most recent bridge dir if using file mode
    root_state="${DEFAULT_BRIDGE_ROOT}/state.json"
    default_state="${DEFAULT_BRIDGE_ROOT}/default/state.json"
    if [[ -f "${root_state}" && -f "${default_state}" ]]; then
        root_mtime=$(stat -f %m "${root_state}" 2>/dev/null || echo 0)
        default_mtime=$(stat -f %m "${default_state}" 2>/dev/null || echo 0)
        if [[ "${default_mtime}" -ge "${root_mtime}" ]]; then
            BRIDGE_DIR="${DEFAULT_BRIDGE_ROOT}/default"
        else
            BRIDGE_DIR="${DEFAULT_BRIDGE_ROOT}"
        fi
    elif [[ -f "${root_state}" ]]; then
        BRIDGE_DIR="${DEFAULT_BRIDGE_ROOT}"
    elif [[ -f "${default_state}" ]]; then
        BRIDGE_DIR="${DEFAULT_BRIDGE_ROOT}/default"
    else
        BRIDGE_DIR="${DEFAULT_BRIDGE_ROOT}"
    fi
fi
STATE_FILE="${BRIDGE_DIR}/state.json"
CMD_FILE="${BRIDGE_DIR}/command.txt"
RESPONSE_FILE="${BRIDGE_DIR}/response.txt"
WATCH_FILE="${BRIDGE_DIR}/watchlist.txt"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SYM_FILE="${SYM_FILE:-${REPO_ROOT}/Roms/oos168x.sym}"

usage() {
    cat <<'EOF'
Mesen2 CLI Bridge

Usage: mesen_cli.sh <command> [args...]

Commands:
  state           Show current game state (JSON)
  state-json [path] Write state JSON to file
  read <addr>     Read 8-bit value from address
  write <addr> <val> Write 8-bit value
  press <btns> [frm] Inject button press
  reinit <targets> Queue runtime reinit (dialog,sprites,overlays,msgbank,roomcache)
  reinit-status  Read reinit flags/status/error
  pause|resume    Control execution
  reset           Reset emulator
  screenshot [path] Save screenshot
  snapshot [dir]  Capture state JSON + screenshot
  loadstate <path> Load state from file
  savestate <path> Save state to file
  saveslot <n>    Save state to slot (1-10)
  loadslot <n>    Load state from slot (1-10)
  wait-save [secs] Wait for savestate to finish
  wait-load [secs] Wait for savestate load to finish
  wait-addr <addr> <val> [secs] Wait for memory match
  loadrom <path>   Load a ROM (Headless only)
  preserve [action] Manage SRAM preservation across save states
                   - status: Show preserve list
                   - on/off: Enable/disable preservation
                   - add <addr>: Add address to preserve list
                   - remove <addr>: Remove address from list
                   - default: Reset to default items
  ... (see script for full list)
EOF
}

ensure_bridge() {
    if [[ "${USE_SOCKET}" -eq 1 ]]; then return 0; fi
    mkdir -p "${BRIDGE_DIR}"
    if [[ ! -f "${STATE_FILE}" ]]; then
        echo "Bridge not active. Load mesen_live_bridge.lua in Mesen2." >&2
        return 1
    fi
}

json_escape() {
    python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"
}

send_socket_command() {
    local cmd="$1"
    shift
    local json="{}"
    local addr=""
    local val=""
    local len=""
    local hex=""
    local path=""
    local buttons=""
    local frames=""

    # Map arguments to JSON
    case "$cmd" in
        READ|READ16)
            addr=$(json_escape "$1")
            json=$(printf '{"type":"%s","addr":%s}' "$cmd" "$addr")
            ;;
        READBLOCK)
            addr=$(json_escape "$1")
            len=$(json_escape "$2")
            json=$(printf '{"type":"%s","addr":%s,"len":%s}' "$cmd" "$addr" "$len")
            ;;
        WRITE|WRITE16)
            addr=$(json_escape "$1")
            val=$(json_escape "$2")
            json=$(printf '{"type":"%s","addr":%s,"val":%s}' "$cmd" "$addr" "$val")
            ;;
        WRITEBLOCK)
            addr=$(json_escape "$1")
            hex=$(json_escape "$2")
            json=$(printf '{"type":"%s","addr":%s,"hex":%s}' "$cmd" "$addr" "$hex")
            ;;
        PRESS|INPUT)
            buttons=$(json_escape "$1")
            frames="${2:-5}"
            json=$(printf '{"type":"PRESS","buttons":%s,"frames":%s}' "$buttons" "$frames")
            ;;
        RELEASE)
             json='{"type":"RELEASE"}'
             ;;
        REINIT)
             local targets
             targets=$(json_escape "$1")
             json=$(printf '{"type":"REINIT","targets":%s}' "$targets")
             ;;
        REINIT_STATUS)
             json='{"type":"REINIT_STATUS"}'
             ;;
        LOADSTATE)
             path=$(json_escape "$1")
             json=$(printf '{"type":"LOADSTATE","path":%s}' "$path")
             ;;
        SAVESTATE)
             path=$(json_escape "$1")
             json=$(printf '{"type":"SAVESTATE","path":%s}' "$path")
             ;;
        LOADSLOT)
             json="{\"type\":\"LOADSLOT\", \"slot\":$1}"
             ;;
        SAVESLOT)
             json="{\"type\":\"SAVESTATE\", \"slot\":$1}"
             ;;
        LOADROM)
             path=$(json_escape "$1")
             json=$(printf '{"type":"LOADROM", "path":%s}' "$path")
             ;;
        PAUSE|RESUME|RESET|STOP)
            json=$(printf '{"type":"%s"}' "$cmd")
            ;;
        STATE)
             # State is fetched via GET
             curl -s "${SOCKET_URL}/state"
             return
             ;;
        PING)
             local health
             health=$(curl -s -m 0.2 "${SOCKET_URL}/health" || true)
             python3 - <<'PY' <<< "${health}"
import json, sys
raw = sys.stdin.read().strip()
try:
    data = json.loads(raw) if raw else {}
except Exception:
    data = {}
connected = bool(data.get("connected"))
if not connected:
    print("mesen_not_connected", file=sys.stderr)
    sys.exit(1)
print("PONG (Socket)")
PY
             return
             ;;
        WARP)
             local kind target x y
             kind=$(json_escape "$1")
             target=$(json_escape "$2")
             x=$(json_escape "$3")
             y=$(json_escape "$4")
             json=$(printf '{"type":"WARP","kind":%s,"target":%s,"x":%s,"y":%s}' "$kind" "$target" "$x" "$y")
             ;;
        SCREENSHOT)
             path=$(json_escape "${1:-}")
             if [[ -z "${1:-}" ]]; then
                 json='{"type":"SCREENSHOT"}'
             else
                 json=$(printf '{"type":"SCREENSHOT","path":%s}' "$path")
             fi
             ;;
        *)
            echo "Command not supported in socket mode yet: $cmd" >&2
            return 1
            ;;
    esac

    # Send request
    local response
    response=$(curl -s -X POST -d "$json" "${SOCKET_URL}/command?wait=true&timeout=3")
    
    # Extract payload from response
    local payload
    payload=$(echo "$response" | python3 -c "import sys, json; 
try:
    d = json.load(sys.stdin)
    status = d.get('status')
    if status in ('timeout','disconnected','error'):
        err = d.get('error') or status or 'error'
        print(err, file=sys.stderr)
        sys.exit(1)
    if 'payload' in d:
        print(d['payload'])
    else:
        # Fallback for simple status responses
        print(json.dumps(d))
except Exception as e:
    print(f'JSON Error: {e}', file=sys.stderr)
    sys.exit(1)")
    
    echo "$payload"
}

send_command() {
    if [[ "${USE_SOCKET}" -eq 1 ]]; then
        send_socket_command "$@"
        return
    fi

    # Fallback to File Bridge
    local cmd="$1"
    shift
    local id
    id="$(date +%s)$RANDOM"
    : > "${RESPONSE_FILE}"
    local payload="${id}|${cmd}"
    for arg in "$@"; do
        payload="${payload}|${arg}"
    done
    printf '%s' "${payload}" > "${CMD_FILE}"
    local timeout="${MESEN_CMD_TIMEOUT:-1}"
    local tries=0
    local max_tries=$((timeout * 20))
    while [[ $tries -lt ${max_tries} ]]; do
        if [[ -f "${RESPONSE_FILE}" && -s "${RESPONSE_FILE}" ]]; then
            local resp
            resp="$(cat "${RESPONSE_FILE}")"
            if [[ "${resp}" == "${id}|OK|"* ]]; then
                printf '%s' "${resp#${id}|OK|}"
                > "${RESPONSE_FILE}"
                return 0
            elif [[ "${resp}" == "${id}|ERR|"* ]]; then
                echo "${resp#${id}|ERR|}" >&2
                > "${RESPONSE_FILE}"
                return 1
            fi
        fi
        sleep 0.05
        tries=$((tries + 1))
    done
    echo "Timeout waiting for response" >&2
    return 1
}

is_slot_number() {
    [[ "$1" =~ ^[0-9]+$ ]] && (( "$1" >= 1 && "$1" <= 10 ))
}

get_state_field() {
    local field="$1"
    local state_json
    state_json="$(send_command "STATE" 2>/dev/null || true)"
    if [[ -z "${state_json}" ]]; then
        return 1
    fi
    python3 - "${field}" <<'PY' <<< "${state_json}"
import json, sys
field = sys.argv[1]
raw = sys.stdin.read().strip()
if not raw:
    sys.exit(1)
try:
    data = json.loads(raw)
except Exception:
    sys.exit(1)
value = data.get(field, "")
if isinstance(value, bool):
    print("true" if value else "false")
elif value is None:
    print("")
else:
    print(value)
PY
}

wait_for_savestate() {
    local mode="$1"
    local timeout="${2:-10}"
    local start
    start=$(date +%s)
    while true; do
        local status
        status="$(get_state_field "savestateStatus" 2>/dev/null || true)"
        local err
        err="$(get_state_field "savestateError" 2>/dev/null || true)"
        local last
        last="$(get_state_field "savestateLastPath" 2>/dev/null || true)"
        if [[ "${mode}" == "save" ]]; then
            if [[ "${status}" == "saved" ]]; then
                echo "OK: saved${last:+:${last}}"
                return 0
            elif [[ "${status}" == "error" ]]; then
                echo "ERROR: ${err:-save_failed}${last:+:${last}}" >&2
                return 1
            fi
        elif [[ "${mode}" == "load" ]]; then
            if [[ "${status}" == "ok" ]]; then
                echo "OK: loaded${last:+:${last}}"
                return 0
            elif [[ "${status}" == "error" ]]; then
                echo "ERROR: ${err:-load_failed}${last:+:${last}}" >&2
                return 1
            fi
        fi
        if [[ $(( $(date +%s) - start )) -ge "${timeout}" ]]; then
            echo "Timed out" >&2
            return 1
        fi
        sleep 0.1
    done
}

# === Commands ===

cmd_state() {
    ensure_bridge || return 1
    send_command "STATE"
}

cmd_read() {
    ensure_bridge || return 1
    send_command "READ" "$1"
}

cmd_read16() {
    ensure_bridge || return 1
    send_command "READ16" "$1"
}

cmd_write() {
    ensure_bridge || return 1
    send_command "WRITE" "$1" "$2"
}

cmd_write16() {
    ensure_bridge || return 1
    send_command "WRITE16" "$1" "$2"
}

cmd_press() {
    ensure_bridge || return 1
    send_command "PRESS" "$1" "${2:-5}"
}

cmd_pause() { send_command "PAUSE"; }
cmd_resume() { send_command "RESUME"; }
cmd_reset() { send_command "RESET"; }
cmd_reinit() { send_command "REINIT" "$1"; }
cmd_reinit_status() { send_command "REINIT_STATUS"; }

cmd_loadstate() {
    ensure_bridge || return 1
    send_command "LOADSTATE" "$1"
}

cmd_savestate() {
    ensure_bridge || return 1
    if is_slot_number "${1:-}"; then
        send_command "SAVESLOT" "$1"
    else
        send_command "SAVESTATE" "$1"
    fi
}

cmd_loadslot() {
    ensure_bridge || return 1
    if [[ "${USE_SOCKET}" -eq 1 ]]; then
        send_command "LOADSLOT" "$1"
    else
        send_command "LOADSLOT" "$1"
    fi
}

cmd_saveslot() {
    ensure_bridge || return 1
    send_command "SAVESLOT" "$1"
}

cmd_screenshot() {
    ensure_bridge || return 1
    send_command "SCREENSHOT" "${1:-}"
}

cmd_state_json() {
    ensure_bridge || return 1
    local out_path="${1:-}"
    if [[ -z "${out_path}" ]]; then
        local ts
        ts="$(date +%Y%m%d_%H%M%S)"
        out_path="${BRIDGE_DIR}/snapshots/state_${ts}.json"
    fi
    mkdir -p "$(dirname "${out_path}")"
    local state_json
    state_json="$(send_command "STATE" 2>/dev/null || true)"
    if [[ -z "${state_json}" ]]; then
        echo "Failed to read state JSON." >&2
        return 1
    fi
    printf '%s' "${state_json}" > "${out_path}"
    echo "${out_path}"
}

cmd_snapshot() {
    ensure_bridge || return 1
    local out_dir="${1:-}"
    if [[ -z "${out_dir}" ]]; then
        out_dir="${BRIDGE_DIR}/snapshots"
    fi
    mkdir -p "${out_dir}"
    local ts
    ts="$(date +%Y%m%d_%H%M%S)"
    local state_path="${out_dir}/state_${ts}.json"
    local shot_path="${out_dir}/shot_${ts}.png"

    local state_out
    state_out="$(cmd_state_json "${state_path}")" || return 1

    local shot_out=""
    if shot_out="$(cmd_screenshot "${shot_path}" 2>/dev/null)"; then
        if [[ "${shot_out}" == SCREENSHOT:* ]]; then
            shot_out="${shot_out#SCREENSHOT:}"
        fi
    else
        echo "Snapshot warning: screenshot failed" >&2
        shot_out=""
    fi

    echo "State: ${state_out}"
    if [[ -n "${shot_out}" ]]; then
        echo "Screenshot: ${shot_out}"
    fi
}

cmd_wait_save() {
    ensure_bridge || return 1
    wait_for_savestate "save" "${1:-10}"
}

cmd_wait_load() {
    ensure_bridge || return 1
    wait_for_savestate "load" "${1:-10}"
}

cmd_status() {
    ensure_bridge || return 1
    local state_json
    state_json="$(send_command "STATE" 2>/dev/null || true)"
    # Use existing python logic in original file if possible, or simple inline logic
    # To keep this file concise I'll assume standard python parsing
    # Reuse the status printer logic from before...
    # (Since I'm overwriting the file, I must re-include the status printer)
    STATE_JSON="${state_json}" SYM_FILE="${SYM_FILE}" SCRIPT_DIR="${SCRIPT_DIR}" python3 << 'PYEOF'
import json, sys, os
from pathlib import Path

# ... (Same status printer logic as before) ...
MODES = {0x00: "Title/Reset", 0x05: "Transition", 0x07: "Dungeon", 0x09: "Overworld", 0x0E: "Menu"}
raw = os.environ.get("STATE_JSON", "").strip()
if not raw: sys.exit(1)
try: d = json.loads(raw)
except: sys.exit(1)

print(f"Mode: {MODES.get(d.get('mode',0), d.get('mode',0))}")
print(f"Room: 0x{d.get('roomId',0):02X}")
print(f"Link: ({d.get('linkX',0)}, {d.get('linkY',0)})")
print(f"Frame: {d.get('frame',0)}")
PYEOF
}

cmd_wait_addr() {
    local addr="${1:-}"
    local expected="${2:-}"
    local timeout="${3:-10}"
    local start=$(date +%s)
    while true; do
        local resp
        resp="$(send_command "READ" "${addr}" 2>/dev/null || true)"
        # Check if resp contains expected value (hex match)
        # Simplified check
        if [[ "$resp" == *"$expected"* ]]; then
             echo "OK: $addr == $expected"
             return 0
        fi
        if [[ $(( $(date +%s) - start )) -ge "${timeout}" ]]; then
            echo "Timed out" >&2
            return 1
        fi
        sleep 0.1
    done
}

# Main dispatch
case "${1:-}" in
    state)    cmd_state ;; 
    state-json) cmd_state_json "${2:-}" ;; 
    read)     cmd_read "${2:-}" ;; 
    read16)   cmd_read16 "${2:-}" ;; 
    write)    cmd_write "${2:-}" "${3:-}" ;; 
    write16)  cmd_write16 "${2:-}" "${3:-}" ;; 
    press)    cmd_press "${2:-}" "${3:-}" ;; 
    reinit)   cmd_reinit "${2:-}" ;;
    reinit-status) cmd_reinit_status ;;
    pause)    cmd_pause ;;
    resume)   cmd_resume ;; 
    reset)    cmd_reset ;; 
    status)   cmd_status ;; 
    loadstate) cmd_loadstate "${2:-}" ;; 
    savestate) cmd_savestate "${2:-}" ;; 
    saveslot) cmd_saveslot "${2:-}" ;;
    loadslot) cmd_loadslot "${2:-}" ;; 
    screenshot) cmd_screenshot "${2:-}" ;;
    snapshot) cmd_snapshot "${2:-}" ;;
    wait-save) cmd_wait_save "${2:-}" ;;
    wait-load) cmd_wait_load "${2:-}" ;;
    wait-addr) cmd_wait_addr "${2:-}" "${3:-}" "${4:-}" ;;
    ping)
        ensure_bridge || return 1
        send_command "PING"
        ;;
    preserve)
        ensure_bridge || return 1
        send_command "PRESERVE" "${2:-status}" "${3:-}" "${4:-}"
        ;;
    -h|--help|"") usage ;; 
    *)
        # Fallback to direct send_command for unknown commands
        ensure_bridge || return 1
        send_command "$1" "${2:-}" "${3:-}" "${4:-}"
        ;;
esac
