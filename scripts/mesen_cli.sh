#!/usr/bin/env bash
# CLI interface to Mesen2 live bridge
# Usage: mesen_cli.sh [command] [args...]

set -euo pipefail

BRIDGE_DIR="${HOME}/Documents/Mesen2/bridge"
STATE_FILE="${BRIDGE_DIR}/state.json"
CMD_FILE="${BRIDGE_DIR}/command.txt"
RESPONSE_FILE="${BRIDGE_DIR}/response.txt"

usage() {
    cat <<'EOF'
Mesen2 CLI Bridge

Usage: mesen_cli.sh <command> [args...]

Commands:
  state           Show current game state (JSON)
  poll [seconds]  Continuously poll state (default: 1s interval)
  read <addr>     Read 8-bit value from address (hex, e.g., 0x7E0010)
  read16 <addr>   Read 16-bit value from address
  ping            Test bridge connection
  lrswap          Check L/R swap test readiness
  watch <addr>    Watch address for changes
  wait-ready      Wait until game is ready for L/R swap test

Examples:
  mesen_cli.sh state
  mesen_cli.sh read 0x7E0739
  mesen_cli.sh poll 0.5
  mesen_cli.sh lrswap
EOF
}

ensure_bridge() {
    mkdir -p "${BRIDGE_DIR}"
    if [[ ! -f "${STATE_FILE}" ]]; then
        echo "Bridge not active. Load mesen_live_bridge.lua in Mesen2 first." >&2
        return 1
    fi
    # Check if state file is recent (within 5 seconds)
    if [[ "$(uname)" == "Darwin" ]]; then
        local age=$(($(date +%s) - $(stat -f %m "${STATE_FILE}")))
    else
        local age=$(($(date +%s) - $(stat -c %Y "${STATE_FILE}")))
    fi
    if [[ $age -gt 5 ]]; then
        echo "Warning: State file is ${age}s old. Is Mesen2 running?" >&2
    fi
}

send_command() {
    local cmd="$1"
    echo -n "${cmd}" > "${CMD_FILE}"
    # Wait for response (up to 1 second)
    local tries=0
    while [[ $tries -lt 20 ]]; do
        if [[ -f "${RESPONSE_FILE}" && -s "${RESPONSE_FILE}" ]]; then
            cat "${RESPONSE_FILE}"
            > "${RESPONSE_FILE}"  # Clear response
            return 0
        fi
        sleep 0.05
        tries=$((tries + 1))
    done
    echo "Timeout waiting for response" >&2
    return 1
}

cmd_state() {
    ensure_bridge || return 1
    cat "${STATE_FILE}"
}

cmd_poll() {
    local interval="${1:-1}"
    ensure_bridge || return 1
    echo "Polling every ${interval}s (Ctrl+C to stop)..."
    while true; do
        clear
        echo "=== Mesen2 Live State ($(date +%H:%M:%S)) ==="
        python3 -c "
import json
with open('${STATE_FILE}') as f:
    d = json.load(f)
print(f\"Frame: {d['frame']}\")
print(f\"Mode: {d['mode']} Sub: {d['submode']} Room: 0x{d['roomId']:02X}\")
print(f\"Link: ({d['linkX']}, {d['linkY']}) State: 0x{d['linkState']:02X} Dir: {d['linkDir']}\")
print(f\"Equipped: Slot {d['equippedSlot']}\")
print(f\"Hookshot SRAM: {d['hookshotSRAM']} (2=both items)\")
gs = 'Goldstar' if d['goldstarOrHookshot'] == 2 else 'Hookshot'
print(f\"Active: {gs}\")
print(f\"Health: {d['health']}/{d['maxHealth']}\")
print(f\"Input F6: 0x{d['inputF6']:02X} (L=0x20, R=0x10)\")
ready = d['hookshotSRAM'] >= 2 and d['equippedSlot'] == 3
print(f\"L/R Swap Ready: {'YES' if ready else 'NO'}\")" 2>/dev/null || cat "${STATE_FILE}"
        sleep "${interval}"
    done
}

cmd_read() {
    local addr="${1:-}"
    if [[ -z "${addr}" ]]; then
        echo "Usage: mesen_cli.sh read <address>" >&2
        return 1
    fi
    ensure_bridge || return 1
    send_command "READ:${addr}"
}

cmd_read16() {
    local addr="${1:-}"
    if [[ -z "${addr}" ]]; then
        echo "Usage: mesen_cli.sh read16 <address>" >&2
        return 1
    fi
    ensure_bridge || return 1
    send_command "READ16:${addr}"
}

cmd_ping() {
    ensure_bridge || return 1
    send_command "PING"
}

cmd_lrswap() {
    ensure_bridge || return 1
    send_command "LRSWAP"
}

cmd_watch() {
    local addr="${1:-}"
    if [[ -z "${addr}" ]]; then
        echo "Usage: mesen_cli.sh watch <address>" >&2
        return 1
    fi
    ensure_bridge || return 1
    echo "Watching ${addr} (Ctrl+C to stop)..."
    local last=""
    while true; do
        local val
        val=$(send_command "READ:${addr}" 2>/dev/null)
        if [[ "${val}" != "${last}" ]]; then
            echo "[$(date +%H:%M:%S.%N | cut -c1-12)] ${val}"
            last="${val}"
        fi
        sleep 0.1
    done
}

cmd_wait_ready() {
    ensure_bridge || return 1
    echo "Waiting for L/R swap test readiness..."
    while true; do
        local result
        result=$(send_command "LRSWAP" 2>/dev/null)
        if [[ "${result}" == *"ready=true"* ]]; then
            echo "Ready! ${result}"
            return 0
        fi
        echo -n "."
        sleep 0.5
    done
}

# Main dispatch
case "${1:-}" in
    state)    cmd_state ;;
    poll)     cmd_poll "${2:-1}" ;;
    read)     cmd_read "${2:-}" ;;
    read16)   cmd_read16 "${2:-}" ;;
    ping)     cmd_ping ;;
    lrswap)   cmd_lrswap ;;
    watch)    cmd_watch "${2:-}" ;;
    wait-ready) cmd_wait_ready ;;
    -h|--help|"") usage ;;
    *)
        echo "Unknown command: $1" >&2
        usage
        exit 1
        ;;
esac
