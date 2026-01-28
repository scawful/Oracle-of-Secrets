#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Launch an isolated Mesen2 OOS instance (safe for multi-agent work).

USAGE:
  scripts/mesen2_launch_instance.sh [options]

OPTIONS:
  --instance NAME        Instance name (default: agent-<timestamp>)
  --owner NAME           Owner label for registry (default: $USER)
  --title TITLE          Window title suffix (default: instance name)
  --source NAME          Agent source tag (default: agent)
  --rom PATH             ROM to load (default: Roms/oos168x.sfc)
  --state-set NAME       Save-state set to apply (default: oos168x_current)
  --state-manifest PATH  Override save-state manifest path
  --no-state-set         Skip applying a save-state set
  --state-allow-partial  Allow missing slots when applying state set
  --state-allow-stale    Allow state set apply even if ROM MD5 mismatches
  --state-force          Overwrite existing states when applying state set
  --allow-stale          Alias for --state-allow-stale
  --force                Alias for --state-force (state apply only)
  --reuse                If socket already exists, do not launch; just print env
  --socket-force         Remove existing socket file (unsafe)
  --lua PATH             Lua script to load on launch
  --home PATH            MESEN2_HOME override (default: platform-specific isolated dir)
  --socket PATH          Socket path override (default: /tmp/mesen2-<instance>.sock)
  --app PATH             Mesen2 OOS.app path override
  --headless             Launch without UI (--headless)
  --no-save-settings     Launch with --doNotSaveSettings
  --copy-settings        Seed settings.json/Input.xml from default profile (default)
  --copy-settings-force  Overwrite settings.json with seeded copy (repairs corrupt configs)
  --no-copy-settings     Skip seeding settings/input from default profile
  --copy-from PATH       Copy settings/input from a specific profile dir
  --allow-default-profile Allow using the default Mesen2 profile/home (unsafe)
  --no-register          Skip mesen2_registry claim
  -h, --help             Show help

ENV OUTPUT:
  The script prints export lines for MESEN2_HOME / MESEN2_SOCKET_PATH / MESEN2_INSTANCE.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

INSTANCE="agent-$(date +%Y%m%d_%H%M%S)"
OWNER="${USER:-agent}"
TITLE=""
TITLE_DEFAULT=0
SOURCE="agent"
ROM_PATH="${ROOT_DIR}/Roms/oos168x.sfc"
STATE_SET="oos168x_current"
STATE_MANIFEST=""
NO_STATE_SET=0
STATE_ALLOW_PARTIAL=0
STATE_ALLOW_STALE=0
STATE_FORCE=0
SOCKET_FORCE=0
REUSE=0
HOME_DIR=""
HOME_DIR_SET=0
SOCKET_PATH=""
SOCKET_PATH_SET=0
APP_PATH="/Applications/Mesen2 OOS.app"
HEADLESS=0
NO_SAVE_SETTINGS=0
ALLOW_DEFAULT_PROFILE=0
REGISTER=1
LUA_SCRIPT=""
COPY_SETTINGS=1
COPY_SETTINGS_FORCE=0
COPY_FROM=""
SETTINGS_STATUS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance) INSTANCE="$2"; shift 2 ;;
    --owner) OWNER="$2"; shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
    --rom) ROM_PATH="$2"; shift 2 ;;
    --state-set) STATE_SET="$2"; shift 2 ;;
    --state-manifest) STATE_MANIFEST="$2"; shift 2 ;;
    --no-state-set) NO_STATE_SET=1; shift ;;
    --state-allow-partial) STATE_ALLOW_PARTIAL=1; shift ;;
    --state-allow-stale) STATE_ALLOW_STALE=1; shift ;;
    --state-force) STATE_FORCE=1; shift ;;
    --allow-stale) STATE_ALLOW_STALE=1; shift ;;
    --force) STATE_FORCE=1; shift ;;
    --reuse) REUSE=1; shift ;;
    --socket-force) SOCKET_FORCE=1; shift ;;
    --lua) LUA_SCRIPT="$2"; shift 2 ;;
    --home) HOME_DIR="$2"; HOME_DIR_SET=1; shift 2 ;;
    --socket) SOCKET_PATH="$2"; SOCKET_PATH_SET=1; shift 2 ;;
    --app) APP_PATH="$2"; shift 2 ;;
    --headless) HEADLESS=1; shift ;;
    --no-save-settings) NO_SAVE_SETTINGS=1; shift ;;
    --copy-settings) COPY_SETTINGS=1; shift ;;
    --copy-settings-force) COPY_SETTINGS=1; COPY_SETTINGS_FORCE=1; shift ;;
    --no-copy-settings) COPY_SETTINGS=0; shift ;;
    --copy-from) COPY_FROM="$2"; shift 2 ;;
    --allow-default-profile) ALLOW_DEFAULT_PROFILE=1; shift ;;
    --no-register) REGISTER=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "${TITLE}" ]]; then
  TITLE="${INSTANCE}"
  TITLE_DEFAULT=1
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
    elif [[ -e "${ROOT_DIR}/${input}" ]]; then
      input="$(cd "${ROOT_DIR}/$(dirname "${input}")" && pwd -P)/$(basename "${input}")"
    fi
  fi
  if [[ -d "${input}" ]]; then
    local found
    found=$(ls "${input}"/oos*x.sfc 2>/dev/null | grep -E 'x\.sfc$' | sort -V | tail -n 1 || true)
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

validate_settings_json() {
  local settings_path="$1"
  python3 - "$settings_path" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
except Exception as exc:
    print(f"settings.json invalid: {exc}", file=sys.stderr)
    sys.exit(1)

if not isinstance(data, dict) or "Input" not in data or "Preferences" not in data:
    print("settings.json missing required keys (Input/Preferences)", file=sys.stderr)
    sys.exit(2)

sys.exit(0)
PY
}

ROM_PATH="$(resolve_rom_path "${ROM_PATH}")"
if [[ ! -f "${ROM_PATH}" ]]; then
  echo "Error: ROM not found: ${ROM_PATH}" >&2
  exit 1
fi

ROM_BASE="$(basename "${ROM_PATH}" | sed 's/\.[^.]*$//')"
if [[ "${ROM_BASE}" == *test* || "${ROM_BASE}" == "oos91x" || "${ROM_BASE}" =~ ^oos[0-9]+$ ]]; then
  echo "Error: refusing to launch editing ROM in Mesen2: ${ROM_PATH}" >&2
  echo "Use the patched ROM (e.g., Roms/oos168x.sfc)." >&2
  exit 1
fi

if [[ -z "${HOME_DIR}" ]]; then
  if [[ "$(uname -s)" == "Darwin" ]]; then
    HOME_DIR="${HOME}/Library/Application Support/Mesen2-instances/${INSTANCE}"
  else
    HOME_DIR="${HOME}/.config/Mesen2-instances/${INSTANCE}"
  fi
fi

if [[ -z "${SOCKET_PATH}" ]]; then
  SOCKET_PATH="/tmp/mesen2-${INSTANCE}.sock"
fi

if [[ -S "${SOCKET_PATH}" ]]; then
  if [[ "${REUSE}" -eq 1 ]]; then
    echo "Socket already exists: ${SOCKET_PATH}"
    echo "Reusing existing instance."
  elif [[ "${SOCKET_FORCE}" -eq 1 ]]; then
    echo "Removing existing socket (unsafe): ${SOCKET_PATH}" >&2
    rm -f "${SOCKET_PATH}"
  else
    suffix="$(date +%Y%m%d_%H%M%S)"
    old_instance="${INSTANCE}"
    INSTANCE="${INSTANCE}-${suffix}"
    if [[ "${TITLE_DEFAULT}" -eq 1 ]]; then
      TITLE="${INSTANCE}"
    fi
    if [[ "${HOME_DIR_SET}" -eq 0 ]]; then
      if [[ "$(uname -s)" == "Darwin" ]]; then
        HOME_DIR="${HOME}/Library/Application Support/Mesen2-instances/${INSTANCE}"
      else
        HOME_DIR="${HOME}/.config/Mesen2-instances/${INSTANCE}"
      fi
    fi
    if [[ "${SOCKET_PATH_SET}" -eq 0 ]]; then
      SOCKET_PATH="/tmp/mesen2-${INSTANCE}.sock"
    fi
    echo "Socket already exists for ${old_instance}; using ${INSTANCE} instead." >&2
  fi
fi

if [[ "${ALLOW_DEFAULT_PROFILE}" -eq 0 ]]; then
  case "${HOME_DIR}" in
    ${HOME}/Documents/Mesen2|${HOME}/Documents/Mesen2/*|\
    ${HOME}/Library/Application\ Support/Mesen2|${HOME}/Library/Application\ Support/Mesen2/*|\
    ${HOME}/.config/Mesen2|${HOME}/.config/Mesen2/*|\
    ${HOME}/.config/mesen2|${HOME}/.config/mesen2/*)
      echo "Error: refusing to use default Mesen2 profile: ${HOME_DIR}" >&2
      echo "Pass --allow-default-profile to override (unsafe)." >&2
      exit 2
      ;;
  esac
fi

mkdir -p "${HOME_DIR}/SaveStates" "${HOME_DIR}/Saves"

if [[ "${COPY_SETTINGS}" -eq 1 ]]; then
  SETTINGS_NEEDS_SEED=1
  if [[ -f "${HOME_DIR}/settings.json" ]]; then
    if validate_settings_json "${HOME_DIR}/settings.json"; then
      SETTINGS_NEEDS_SEED=0
    else
      ts="$(date +%Y%m%d_%H%M%S)"
      mv "${HOME_DIR}/settings.json" "${HOME_DIR}/settings.json.invalid-${ts}"
      SETTINGS_NEEDS_SEED=1
    fi
  fi
  if [[ "${COPY_SETTINGS_FORCE}" -eq 1 ]]; then
    SETTINGS_NEEDS_SEED=1
  fi

  if [[ -z "${COPY_FROM}" ]]; then
    for candidate in \
      "${HOME}/Documents/Mesen2" \
      "${HOME}/Library/Application Support/Mesen2" \
      "${HOME}/.config/Mesen2"; do
      if [[ -f "${candidate}/settings.json" ]]; then
        COPY_FROM="${candidate}"
        break
      fi
    done
  fi

  if [[ -n "${COPY_FROM}" ]]; then
    if [[ "${SETTINGS_NEEDS_SEED}" -eq 1 && -f "${COPY_FROM}/settings.json" ]]; then
      cp "${COPY_FROM}/settings.json" "${HOME_DIR}/settings.json"
      echo "Seeded settings.json from ${COPY_FROM} (source profile untouched)"
      SETTINGS_STATUS="seeded from ${COPY_FROM}"
    elif [[ "${SETTINGS_NEEDS_SEED}" -eq 1 ]]; then
      echo "Warning: settings.json not found at ${COPY_FROM} (input prefs may reset)." >&2
      SETTINGS_STATUS="missing source (input prefs may reset)"
    else
      SETTINGS_STATUS="existing config"
    fi
    if [[ -f "${COPY_FROM}/Input.xml" && ! -f "${HOME_DIR}/Input.xml" ]]; then
      cp "${COPY_FROM}/Input.xml" "${HOME_DIR}/Input.xml"
      echo "Seeded Input.xml from ${COPY_FROM}"
    fi
    if [[ -f "${COPY_FROM}/instance_guid.txt" && ! -f "${HOME_DIR}/instance_guid.txt" ]]; then
      cp "${COPY_FROM}/instance_guid.txt" "${HOME_DIR}/instance_guid.txt"
    fi
  else
    if [[ "${SETTINGS_NEEDS_SEED}" -eq 0 ]]; then
      SETTINGS_STATUS="existing config"
    else
      echo "Warning: no default Mesen2 profile found to seed settings/input." >&2
      SETTINGS_STATUS="missing source (input prefs may reset)"
    fi
  fi
else
  SETTINGS_STATUS="copy disabled"
fi

if [[ "${NO_STATE_SET}" -eq 0 ]]; then
  set_cmd=(python3 "${ROOT_DIR}/scripts/state_library.py" set-apply --set "${STATE_SET}")
  if [[ -n "${STATE_MANIFEST}" ]]; then
    set_cmd+=(--manifest "${STATE_MANIFEST}")
  fi
  set_cmd+=(--mesen-dir "${HOME_DIR}/SaveStates" --mesen-saves-dir "${HOME_DIR}/Saves")
  set_cmd+=(--rom "${ROM_PATH}")
  if [[ "${STATE_ALLOW_PARTIAL}" -eq 1 ]]; then
    set_cmd+=(--allow-partial)
  fi
  if [[ "${STATE_ALLOW_STALE}" -eq 1 ]]; then
    set_cmd+=(--allow-stale)
  fi
  if [[ "${STATE_FORCE}" -eq 1 ]]; then
    set_cmd+=(--force)
  fi
  echo "Applying state set '${STATE_SET}' to ${HOME_DIR}/SaveStates..."
  "${set_cmd[@]}"
fi

MESEN_BIN=""
if [[ -d "${APP_PATH}" ]]; then
  for candidate in \
    "${APP_PATH}/Contents/MacOS/Mesen2" \
    "${APP_PATH}/Contents/MacOS/Mesen" \
    "${APP_PATH}/Contents/MacOS/Mesen2 OOS"; do
    if [[ -x "${candidate}" ]]; then
      MESEN_BIN="${candidate}"
      break
    fi
  done
fi

if [[ -z "${MESEN_BIN}" ]]; then
  fallback_app="${HOME}/src/hobby/mesen2-oos/bin/osx-arm64/Release/osx-arm64/publish/Mesen2 OOS.app"
  if [[ -d "${fallback_app}" ]]; then
    for candidate in \
      "${fallback_app}/Contents/MacOS/Mesen2" \
      "${fallback_app}/Contents/MacOS/Mesen" \
      "${fallback_app}/Contents/MacOS/Mesen2 OOS"; do
      if [[ -x "${candidate}" ]]; then
        MESEN_BIN="${candidate}"
        APP_PATH="${fallback_app}"
        break
      fi
    done
  fi
fi

if [[ -z "${MESEN_BIN}" ]]; then
  echo "Error: Mesen2 OOS binary not found. Use --app to point at Mesen2 OOS.app." >&2
  exit 1
fi

export MESEN2_HOME="${HOME_DIR}"
export MESEN2_SOCKET_PATH="${SOCKET_PATH}"
export MESEN2_INSTANCE="${INSTANCE}"
export MESEN2_AGENT_TITLE="${TITLE}"
export MESEN2_AGENT_SOURCE="${SOURCE}"
export MESEN2_AGENT_ACTIVE=1

echo "==================================="
echo " Mesen2 OOS Isolated Instance"
echo "==================================="
echo "Instance: ${INSTANCE}"
echo "Owner:    ${OWNER}"
echo "Title:    ${TITLE}"
echo "Source:   ${SOURCE}"
echo "ROM:      ${ROM_PATH}"
echo "Settings: ${SETTINGS_STATUS}"
echo "Home:     ${HOME_DIR}"
echo "Socket:   ${SOCKET_PATH}"
echo "Binary:   ${MESEN_BIN}"
echo "==================================="

launch_args=("${ROM_PATH}" "--instanceName=${INSTANCE}" "--multiinstance")
if [[ -n "${LUA_SCRIPT}" ]]; then
  launch_args+=("${LUA_SCRIPT}")
fi
if [[ "${HEADLESS}" -eq 1 ]]; then
  launch_args+=("--headless")
fi
if [[ "${NO_SAVE_SETTINGS}" -eq 1 ]]; then
  launch_args+=("--doNotSaveSettings")
fi

if [[ "${REUSE}" -eq 0 ]]; then
  if command -v nohup >/dev/null 2>&1; then
    nohup "${MESEN_BIN}" "${launch_args[@]}" >/tmp/mesen2_"${INSTANCE}".log 2>&1 &
  else
    "${MESEN_BIN}" "${launch_args[@]}" >/tmp/mesen2_"${INSTANCE}".log 2>&1 &
  fi
  # Prevent SIGHUP from killing the background process when the shell exits.
  if [[ -n "${BASH_VERSION:-}" ]]; then
    disown || true
  fi
fi

if [[ "${REGISTER}" -eq 1 ]]; then
  registry="${ROOT_DIR}/scripts/mesen2_registry.py"
  if [[ -f "${registry}" ]]; then
    # wait briefly for socket
    for _ in {1..40}; do
      if [[ -S "${SOCKET_PATH}" ]]; then
        break
      fi
      sleep 0.25
    done
    python3 "${registry}" claim \
      --instance "${INSTANCE}" \
      --owner "${OWNER}" \
      --socket "${SOCKET_PATH}" \
      --rom "${ROM_PATH}" \
      --app-name "Mesen2 OOS" \
      --app-path "${APP_PATH}" \
      --active \
      --source "${SOURCE}" || true
  fi
fi

echo ""
echo "Exports:"
echo "  export MESEN2_HOME=\"${MESEN2_HOME}\""
echo "  export MESEN2_SOCKET_PATH=\"${MESEN2_SOCKET_PATH}\""
echo "  export MESEN2_INSTANCE=\"${MESEN2_INSTANCE}\""
echo ""
echo "Verify:"
echo "  python3 ${ROOT_DIR}/scripts/mesen2_client.py --socket \"${MESEN2_SOCKET_PATH}\" health"
