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
  status          Human-readable game status
  poll [seconds]  Continuously poll state (default: 1s interval)
  read <addr>     Read 8-bit value from address (hex, e.g., 0x7E0010)
  read16 <addr>   Read 16-bit value from address
  readblock <addr> <len>  Read a block of bytes (hex string)
  write <addr> <value>    Write 8-bit value to address
  write16 <addr> <value>  Write 16-bit value to address
  press <buttons> [frames]  Inject button press (default: 5 frames)
  release         Stop any injected input
  ping            Test bridge connection
  lrswap          Check L/R swap test readiness
  watch <addr>    Watch address for changes
  wait-ready      Wait until game is ready for L/R swap test

Button Names: A, B, X, Y, L, R, UP, DOWN, LEFT, RIGHT, START, SELECT
Combine with +: A+B, UP+A, L+R+START

Examples:
  mesen_cli.sh state
  mesen_cli.sh read 0x7E0739
  mesen_cli.sh press A             # Press A for 5 frames
  mesen_cli.sh press START 1       # Press Start for 1 frame
  mesen_cli.sh press UP+A 10       # Press Up+A for 10 frames
  mesen_cli.sh poll 0.5
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
    shift
    local id
    id="$(date +%s)$RANDOM"
    : > "${RESPONSE_FILE}"
    local payload="${id}|${cmd}"
    for arg in "$@"; do
        payload="${payload}|${arg}"
    done
    printf '%s' "${payload}" > "${CMD_FILE}"
    # Wait for response (up to 1 second)
    local tries=0
    while [[ $tries -lt 20 ]]; do
        if [[ -f "${RESPONSE_FILE}" && -s "${RESPONSE_FILE}" ]]; then
            local resp
            resp="$(cat "${RESPONSE_FILE}")"
            if [[ "${resp}" == "${id}|OK|"* ]]; then
                printf '%s' "${resp#${id}|OK|}"
                > "${RESPONSE_FILE}"  # Clear response
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

cmd_state() {
    ensure_bridge || return 1
    send_command "STATE"
}

cmd_poll() {
    local interval="${1:-1}"
    ensure_bridge || return 1
    echo "Polling every ${interval}s (Ctrl+C to stop)..."
    while true; do
        clear
        echo "=== Mesen2 Live State ($(date +%H:%M:%S)) ==="
        local state_json
        state_json="$(send_command "STATE" 2>/dev/null || true)"
        python3 -c "
import json
import sys
raw = sys.stdin.read().strip()
if not raw:
    sys.exit(1)
d = json.loads(raw)
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
print(f\"L/R Swap Ready: {'YES' if ready else 'NO'}\")" <<< "${state_json}" 2>/dev/null || echo "${state_json}"
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
    send_command "READ" "${addr}"
}

cmd_read16() {
    local addr="${1:-}"
    if [[ -z "${addr}" ]]; then
        echo "Usage: mesen_cli.sh read16 <address>" >&2
        return 1
    fi
    ensure_bridge || return 1
    send_command "READ16" "${addr}"
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
        val=$(send_command "READ" "${addr}" 2>/dev/null)
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

cmd_status() {
    ensure_bridge || return 1
    local state_json
    state_json="$(send_command "STATE" 2>/dev/null || true)"
    STATE_JSON="${state_json}" python3 << 'PYEOF'
import json
import sys
import os

# Game mode translations
MODES = {
    0x00: "Title/Reset",
    0x05: "Transition (Loading)",
    0x07: "Dungeon",
    0x09: "Overworld",
    0x0B: "Submenu (Inventory/Map)",
    0x0E: "Menu/Dialog",
    0x10: "Cutscene",
    0x12: "Special Effect",
    0x14: "Game Over",
    0x17: "Triforce Fanfare",
    0x19: "Credits"
}

DIRECTIONS = {0: "Up", 2: "Down", 4: "Left", 6: "Right"}

LINK_STATES = {
    0x00: "Standing/Idle",
    0x01: "Walking",
    0x02: "Walking (alt)",
    0x04: "Swimming",
    0x08: "Jumping",
    0x0D: "Attacking",
    0x13: "Hookshot Extended",
    0x14: "Recoil/Damage",
    0x17: "Falling",
    0x1C: "Pushing",
    0x1F: "Item Use"
}

raw = os.environ.get("STATE_JSON", "").strip()
if not raw:
    print("Error reading state: empty response")
    sys.exit(1)
try:
    d = json.loads(raw)
except Exception as e:
    print(f"Error reading state: {e}")
    sys.exit(1)

print("=" * 50)
print("ORACLE OF SECRETS - Game Status")
print("=" * 50)

# Game Mode
mode = d.get("mode", 0)
mode_name = MODES.get(mode, f"Unknown (0x{mode:02X})")
print(f"\n[Game Mode] {mode_name}")
print(f"  Submode: {d.get('submode', 0)}")
print(f"  Location: {'Indoors' if d.get('indoors') else 'Outdoors'}")
print(f"  Room ID: 0x{d.get('roomId', 0):02X}")

# Link Status
link_state = d.get("linkState", 0)
state_name = LINK_STATES.get(link_state, f"Unknown (0x{link_state:02X})")
direction = DIRECTIONS.get(d.get("linkDir", 0), "Unknown")
print(f"\n[Link]")
print(f"  Position: ({d.get('linkX', 0)}, {d.get('linkY', 0)})")
print(f"  Facing: {direction}")
print(f"  State: {state_name}")
health = d.get("health", 0)
max_health = d.get("maxHealth", 0)
hearts = health // 8
max_hearts = max_health // 8
print(f"  Health: {hearts}/{max_hearts} hearts ({health}/{max_health} raw)")

# Equipment (L/R Swap relevant)
print(f"\n[Equipment - L/R Swap]")
gs_val = d.get("goldstarOrHookshot", 0)
if gs_val == 2:
    active = "Goldstar (can switch)"
elif gs_val == 1:
    active = "Hookshot (can switch)"
else:
    active = "Hookshot (default/unset)"
print(f"  Active Item: {active}")

sram = d.get("hookshotSRAM", 0)
if sram == 2:
    ownership = "Both Hookshot AND Goldstar"
elif sram == 1:
    ownership = "Hookshot only"
else:
    ownership = "Neither item"
print(f"  Ownership: {ownership}")

slot = d.get("equippedSlot", 0)
print(f"  Menu Slot: {slot} {'(Hookshot slot)' if slot == 3 else ''}")

# L/R Swap Test Readiness
ready = sram >= 2 and slot == 3
print(f"\n[L/R Swap Test]")
if ready:
    print("  Status: READY - Press L or R to toggle!")
else:
    reasons = []
    if sram < 2:
        reasons.append("Need both Hookshot and Goldstar")
    if slot != 3:
        reasons.append(f"Select Hookshot slot (currently {slot})")
    print("  Status: NOT READY")
    for r in reasons:
        print(f"    - {r}")

# Input State
print(f"\n[Input]")
f6 = d.get("inputF6", 0)
inputs = []
if f6 & 0x80: inputs.append("A")
if f6 & 0x40: inputs.append("X")
if f6 & 0x20: inputs.append("L")
if f6 & 0x10: inputs.append("R")
print(f"  New This Frame: {', '.join(inputs) if inputs else 'None'}")

print(f"\n[Frame: {d.get('frame', 0)}]")
print("=" * 50)
PYEOF
}

# New commands
cmd_readblock() {
    local addr="${1:-}"
    local len="${2:-}"
    if [[ -z "${addr}" || -z "${len}" ]]; then
        echo "Usage: mesen_cli.sh readblock <address> <length>" >&2
        return 1
    fi
    ensure_bridge || return 1
    send_command "READBLOCK" "${addr}" "${len}"
}

cmd_write() {
    local addr="${1:-}"
    local value="${2:-}"
    if [[ -z "${addr}" || -z "${value}" ]]; then
        echo "Usage: mesen_cli.sh write <address> <value>" >&2
        return 1
    fi
    ensure_bridge || return 1
    send_command "WRITE" "${addr}" "${value}"
}

cmd_write16() {
    local addr="${1:-}"
    local value="${2:-}"
    if [[ -z "${addr}" || -z "${value}" ]]; then
        echo "Usage: mesen_cli.sh write16 <address> <value>" >&2
        return 1
    fi
    ensure_bridge || return 1
    send_command "WRITE16" "${addr}" "${value}"
}

cmd_press() {
    local buttons="${1:-}"
    local frames="${2:-5}"
    if [[ -z "${buttons}" ]]; then
        echo "Usage: mesen_cli.sh press <buttons> [frames]" >&2
        echo "Buttons: A, B, X, Y, L, R, UP, DOWN, LEFT, RIGHT, START, SELECT" >&2
        echo "Combine: A+B, UP+A, L+R+START" >&2
        return 1
    fi
    ensure_bridge || return 1
    send_command "INPUT" "${buttons}" "${frames}"
}

cmd_release() {
    ensure_bridge || return 1
    send_command "RELEASE"
}

cmd_watergate() {
    ensure_bridge || return 1
    local state_json
    state_json="$(send_command "STATE" 2>/dev/null || true)"
    local room
    room="$(python3 -c 'import json,sys; d=json.loads(sys.stdin.read() or "{}"); print(d.get("roomId",-1))' <<< "${state_json}")"
    if [[ "${room}" != "39" ]]; then
        echo "Not in room 0x27 (decimal 39). Current room: ${room}"
    fi

    local sram
    sram="$(send_command "READ" "0x7EF411" 2>/dev/null || true)"
    echo "SRAM WaterGateStates: ${sram}"

    local offsets=(0x0A45 0x0A58 0x0A79 0x0A95 0x0AD5)
    local ok=1
    for off in "${offsets[@]}"; do
        local addr=$((0x7F2000 + off))
        local resp
        resp="$(send_command "READ" "$(printf '0x%06X' "${addr}")" 2>/dev/null || true)"
        local hex
        hex="$(echo "${resp}" | sed -E 's/.*=0x([0-9A-Fa-f]{2}).*/\1/')"
        printf 'COLMAPA[0x%04X] = 0x%s\n' "${off}" "${hex}"
        if [[ "${hex^^}" != "08" ]]; then
            ok=0
        fi
    done

    if [[ "${ok}" -eq 1 ]]; then
        echo "Water gate sample collisions: PASS ($08)"
    else
        echo "Water gate sample collisions: FAIL"
        return 1
    fi
}

# Main dispatch
case "${1:-}" in
    state)    cmd_state ;;
    status)   cmd_status ;;
    poll)     cmd_poll "${2:-1}" ;;
    read)     cmd_read "${2:-}" ;;
    read16)   cmd_read16 "${2:-}" ;;
    readblock) cmd_readblock "${2:-}" "${3:-}" ;;
    write)    cmd_write "${2:-}" "${3:-}" ;;
    write16)  cmd_write16 "${2:-}" "${3:-}" ;;
    press)    cmd_press "${2:-}" "${3:-}" ;;
    release)  cmd_release ;;
    ping)     cmd_ping ;;
    lrswap)   cmd_lrswap ;;
    watch)    cmd_watch "${2:-}" ;;
    wait-ready) cmd_wait_ready ;;
    watergate) cmd_watergate ;;
    -h|--help|"") usage ;;
    *)
        echo "Unknown command: $1" >&2
        usage
        exit 1
        ;;
esac
