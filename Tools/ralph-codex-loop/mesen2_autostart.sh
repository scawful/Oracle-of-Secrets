#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ROM_DEFAULT="${ROOT_DIR}/Roms/oos168x.sfc"
ROM_PATH="${RALPH_ROM:-$ROM_DEFAULT}"
LUA_SCRIPT="${RALPH_LUA:-}"

INSTANCE="${RALPH_MESEN2_INSTANCE:-agent}"
OWNER="${RALPH_MESEN2_OWNER:-agent}"
APP_PATH="${RALPH_MESEN2_APP:-}"
HEADLESS="${RALPH_HEADLESS:-0}"
CLEAN="${RALPH_CLEAN:-0}"

REGISTRY="${ROOT_DIR}/scripts/mesen2_registry.py"
LAUNCHER="${ROOT_DIR}/scripts/mesen2_launch_instance.sh"

if [[ "${CLEAN}" == "1" && -f "${REGISTRY}" ]]; then
  python3 "${REGISTRY}" close --instance "${INSTANCE}" --owner "${OWNER}" --force >/dev/null 2>&1 || true
  python3 "${REGISTRY}" prune >/dev/null 2>&1 || true
fi

args=(--instance "${INSTANCE}" --owner "${OWNER}" --rom "${ROM_PATH}")
if [[ -n "${APP_PATH}" ]]; then
  args+=(--app "${APP_PATH}")
fi
if [[ -n "${LUA_SCRIPT}" ]]; then
  args+=(--lua "${LUA_SCRIPT}")
fi
if [[ "${HEADLESS}" == "1" ]]; then
  args+=(--headless)
fi

if [[ ! -x "${LAUNCHER}" ]]; then
  echo "Missing launcher: ${LAUNCHER}" >&2
  exit 1
fi

"${LAUNCHER}" "${args[@]}"

echo "Launched Mesen2 instance=${INSTANCE} ROM=${ROM_PATH} ${LUA_SCRIPT:+LUA=${LUA_SCRIPT}}"
