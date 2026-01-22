#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: sync_mesen_saves.sh [--target oos168] [--with-patched] [--force]\n                           [--rom PATH] [--source-rom PATH] [--allow-stale]

Copies oos91x save states/srm into the Mesen2 folders, renaming to a new base.

Options:
  --target NAME     Base ROM name to copy to (default: oos168)
  --with-patched    Also copy to NAME + "x" (patched ROM)
  --force           Overwrite existing files
  --rom PATH        Target ROM path (for MD5 check)
  --source-rom PATH Source ROM path (for MD5 check)
  --allow-stale     Allow copying across ROM MD5 mismatch

Env:
  MESEN2_DIR        Destination base (default: ~/Documents/Mesen2)
EOF
}

TARGET="oos168"
WITH_PATCHED=0
FORCE=0
ALLOW_STALE=0
ROM_PATH=""
SOURCE_ROM_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="${2:-}"
      shift 2
      ;;
    --with-patched)
      WITH_PATCHED=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --rom)
      ROM_PATH="${2:-}"
      shift 2
      ;;
    --source-rom)
      SOURCE_ROM_PATH="${2:-}"
      shift 2
      ;;
    --allow-stale)
      ALLOW_STALE=1
      shift
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
SRC_DIR="${REPO_ROOT}/Roms/SaveStates/oos91x"
MESEN2_DIR="${MESEN2_DIR:-$HOME/Documents/Mesen2}"
DST_STATES="${MESEN2_DIR}/SaveStates"
DST_SAVES="${MESEN2_DIR}/Saves"

hash_file() {
  local path="$1"
  if command -v md5 >/dev/null 2>&1; then
    md5 -q "$path"
  elif command -v md5sum >/dev/null 2>&1; then
    md5sum "$path" | awk '{print $1}'
  else
    echo ""
  fi
}

if [[ ! -d "${SRC_DIR}" ]]; then
  echo "Missing source dir: ${SRC_DIR}" >&2
  exit 1
fi

SOURCE_BASE="$(basename "${SRC_DIR}")"
if [[ -z "${ROM_PATH}" ]]; then
  ROM_PATH="${REPO_ROOT}/Roms/${TARGET}.sfc"
  [[ -f "${ROM_PATH}" ]] || ROM_PATH=""
fi

if [[ -z "${SOURCE_ROM_PATH}" ]]; then
  SOURCE_ROM_PATH="${REPO_ROOT}/Roms/${SOURCE_BASE}.sfc"
  [[ -f "${SOURCE_ROM_PATH}" ]] || SOURCE_ROM_PATH=""
fi

if [[ -n "${ROM_PATH}" && -n "${SOURCE_ROM_PATH}" ]]; then
  TARGET_MD5="$(hash_file "${ROM_PATH}")"
  SOURCE_MD5="$(hash_file "${SOURCE_ROM_PATH}")"
  if [[ -n "${TARGET_MD5}" && -n "${SOURCE_MD5}" && "${TARGET_MD5}" != "${SOURCE_MD5}" ]]; then
    if [[ "${ALLOW_STALE}" -eq 0 ]]; then
      echo "ROM MD5 mismatch: source ${SOURCE_MD5} != target ${TARGET_MD5}" >&2
      echo "Refusing to copy. Use --allow-stale to override." >&2
      exit 1
    fi
    echo "WARNING: ROM MD5 mismatch (source ${SOURCE_MD5} -> target ${TARGET_MD5}); copying anyway." >&2
  fi
fi

mkdir -p "${DST_STATES}" "${DST_SAVES}"

copy_file() {
  local src="$1"
  local dst="$2"

  if [[ -e "${dst}" && "${FORCE}" -eq 0 ]]; then
    return
  fi
  cp -f "${src}" "${dst}"
}

shopt -s nullglob
for f in "${SRC_DIR}"/oos91x_*.mss; do
  base="$(basename "${f}")"
  num="${base#oos91x_}"
  copy_file "${f}" "${DST_STATES}/${TARGET}_${num}"
  if [[ "${WITH_PATCHED}" -eq 1 ]]; then
    copy_file "${f}" "${DST_STATES}/${TARGET}x_${num}"
  fi
done

if [[ -f "${SRC_DIR}/oos91x.srm" ]]; then
  copy_file "${SRC_DIR}/oos91x.srm" "${DST_SAVES}/${TARGET}.srm"
  if [[ "${WITH_PATCHED}" -eq 1 ]]; then
    copy_file "${SRC_DIR}/oos91x.srm" "${DST_SAVES}/${TARGET}x.srm"
  fi
fi
