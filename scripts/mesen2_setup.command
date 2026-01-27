#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: mesen2_setup.command [--rom PATH]

Opens Mesen2 with a ROM and pops open the Scripts/SaveStates folders.

Env:
  MESEN_APP   Override Mesen app path
  MESEN2_DIR  Override Mesen2 data directory
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

APP_PATH="${MESEN_APP:-}"
DEFAULT_ROM="${REPO_ROOT}/Roms/oos168x.sfc"
ROM_PATH="${ROM_OVERRIDE:-$DEFAULT_ROM}"

MESEN2_DIR="${MESEN2_DIR:-}"

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

resolve_mesen_app() {
  if [[ -n "${APP_PATH}" ]]; then
    echo "${APP_PATH}"
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
  local app_support="${HOME}/Library/Application Support/Mesen2"
  if [[ -d "${app_support}" ]]; then
    echo "${app_support}"
    return
  fi
  echo "${HOME}/Documents/Mesen2"
}

APP_PATH="$(resolve_mesen_app)"
MESEN2_DIR="$(resolve_mesen_dir)"
ROM_PATH="$(resolve_rom_path "${ROM_PATH}")"

SCRIPTS_DIR="${MESEN2_DIR}/Scripts"
STATES_DIR="${MESEN2_DIR}/SaveStates"
SAVES_DIR="${MESEN2_DIR}/Saves"

mkdir -p "${SCRIPTS_DIR}" "${STATES_DIR}" "${SAVES_DIR}"

if [[ ! -d "${APP_PATH}" ]]; then
  echo "Mesen app not found: ${APP_PATH}" >&2
  exit 1
fi

if [[ ! -f "${ROM_PATH}" ]]; then
  echo "ROM not found: ${ROM_PATH}" >&2
  echo "Tip: pass a directory (it will search for the latest oos*x.sfc patched ROM)." >&2
  exit 1
fi

ROM_BASE="$(basename "${ROM_PATH}" | sed 's/\.[^.]*$//')"
if [[ "${ROM_BASE}" == *test* || "${ROM_BASE}" == "oos91x" || "${ROM_BASE}" =~ ^oos[0-9]+$ ]]; then
  echo "Refusing to launch editing ROM in Mesen2: ${ROM_PATH}" >&2
  echo "Use the patched ROM (e.g., Roms/oos168x.sfc)." >&2
  exit 1
fi

open -a "${APP_PATH}" "${ROM_PATH}"
open "${SCRIPTS_DIR}"
open "${STATES_DIR}"
open "${SAVES_DIR}"

osascript <<'APPLESCRIPT'
display dialog "Mesen2 is open.\n\nNext:\n1) Load script: ~/Documents/Mesen2/Scripts/mesen_water_debug.lua\n2) Load state: oos168x_1.mss (or any oos168x_*.mss)\n\nTell Codex once the overlay shows." buttons {"OK"} default button 1
APPLESCRIPT
