#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: mesen2_setup.command [--rom PATH]

Opens Mesen2 with a ROM and pops open the Scripts/SaveStates folders.

Env:
  MESEN_APP   Override Mesen app path (default: /Applications/Mesen.app)
EOF
}

ROM_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --rom)
      ROM_OVERRIDE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

APP_PATH="${MESEN_APP:-/Applications/Mesen.app}"
DEFAULT_ROM="${REPO_ROOT}/Roms/oos168x.sfc"
ROM_PATH="${ROM_OVERRIDE:-$DEFAULT_ROM}"

SCRIPTS_DIR="$HOME/Documents/Mesen2/Scripts"
STATES_DIR="$HOME/Documents/Mesen2/SaveStates"
SAVES_DIR="$HOME/Documents/Mesen2/Saves"

mkdir -p "${SCRIPTS_DIR}" "${STATES_DIR}" "${SAVES_DIR}"

if [[ ! -d "${APP_PATH}" ]]; then
  echo "Mesen app not found: ${APP_PATH}" >&2
  exit 1
fi

if [[ ! -f "${ROM_PATH}" ]]; then
  echo "ROM not found: ${ROM_PATH}" >&2
  exit 1
fi

open -a "${APP_PATH}" "${ROM_PATH}"
open "${SCRIPTS_DIR}"
open "${STATES_DIR}"
open "${SAVES_DIR}"

osascript <<'APPLESCRIPT'
display dialog "Mesen2 is open.\n\nNext:\n1) Load script: ~/Documents/Mesen2/Scripts/mesen_water_debug.lua\n2) Load state: oos168x_1.mss (or any oos168x_*.mss)\n\nTell Codex once the overlay shows." buttons {"OK"} default button 1
APPLESCRIPT
