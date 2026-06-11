#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: Scripts/beta_patch.sh [version] [options]

Build a beta-ready BPS patch plus metadata and notes stub.

Options:
  --out-dir DIR     Output directory (default: build/releases)
  --skip-build      Reuse existing ROMs instead of rebuilding first
  --notes PATH      Override notes stub path
  -h, --help        Show this help

Examples:
  Scripts/beta_patch.sh
  Scripts/beta_patch.sh 168
  Scripts/beta_patch.sh 168 --skip-build
  Scripts/beta_patch.sh 168 --out-dir /tmp/oos-release
EOF
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_SCRIPT="${ROOT_DIR}/Scripts/Build/build_rom.sh"
OVERLAP_CHECK="${ROOT_DIR}/Scripts/Build/check_zscream_overlap.py"

VERSION="${OOS_BUILD_VERSION:-168}"
OUT_DIR="${ROOT_DIR}/build/releases"
SKIP_BUILD=0
NOTES_PATH=""

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 0 && "${1}" =~ ^[0-9]+$ ]]; then
  VERSION="${1}"
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    --notes)
      NOTES_PATH="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

resolve_base_rom() {
  local version="$1"
  local rom_dir="${ROOT_DIR}/Roms"
  local default_base="${rom_dir}/oos${version}.sfc"
  local legacy_base="${rom_dir}/oos${version}_test2.sfc"

  if [[ -n "${OOS_BASE_ROM:-}" ]]; then
    printf '%s\n' "${OOS_BASE_ROM}"
    return
  fi
  if [[ -f "${default_base}" ]]; then
    printf '%s\n' "${default_base}"
    return
  fi
  if [[ -f "${legacy_base}" ]]; then
    printf '%s\n' "${legacy_base}"
    return
  fi
  printf '%s\n' "${default_base}"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: required command not found: $1" >&2
    exit 1
  fi
}

hash_file() {
  local path="$1"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$path" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$path" | awk '{print $1}'
  else
    echo "Error: no SHA-256 tool found (need shasum or sha256sum)" >&2
    exit 1
  fi
}

require_cmd flips

BASE_ROM="$(resolve_base_rom "${VERSION}")"
PATCHED_ROM="${ROOT_DIR}/Roms/oos${VERSION}x.sfc"

if [[ "${SKIP_BUILD}" != "1" ]]; then
  "${BUILD_SCRIPT}" "${VERSION}"
elif [[ -f "${OVERLAP_CHECK}" ]]; then
  python3 "${OVERLAP_CHECK}"
fi

if [[ ! -f "${BASE_ROM}" ]]; then
  echo "Error: base ROM not found: ${BASE_ROM}" >&2
  exit 1
fi
if [[ ! -f "${PATCHED_ROM}" ]]; then
  echo "Error: patched ROM not found: ${PATCHED_ROM}" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

STAMP="$(date +%Y%m%d_%H%M%S)"
ARTIFACT_STEM="oos${VERSION}_beta_${STAMP}"
PATCH_PATH="${OUT_DIR}/${ARTIFACT_STEM}.bps"
MANIFEST_PATH="${OUT_DIR}/${ARTIFACT_STEM}.json"
if [[ -z "${NOTES_PATH}" ]]; then
  NOTES_PATH="${OUT_DIR}/${ARTIFACT_STEM}_notes.md"
fi

echo "[beta-patch] Creating BPS patch..."
flips --create --bps "${BASE_ROM}" "${PATCHED_ROM}" "${PATCH_PATH}"

BASE_SHA="$(hash_file "${BASE_ROM}")"
PATCHED_SHA="$(hash_file "${PATCHED_ROM}")"
PATCH_SHA="$(hash_file "${PATCH_PATH}")"

cat >"${MANIFEST_PATH}" <<EOF
{
  "created_at": "${STAMP}",
  "version": ${VERSION},
  "base_rom": "$(basename "${BASE_ROM}")",
  "patched_rom": "$(basename "${PATCHED_ROM}")",
  "patch_file": "$(basename "${PATCH_PATH}")",
  "base_sha256": "${BASE_SHA}",
  "patched_sha256": "${PATCHED_SHA}",
  "patch_sha256": "${PATCH_SHA}",
  "notes_file": "$(basename "${NOTES_PATH}")"
}
EOF

if [[ ! -f "${NOTES_PATH}" ]]; then
  cat >"${NOTES_PATH}" <<EOF
# Oracle of Secrets Beta Patch

- Build date: ${STAMP}
- Internal ROM version: ${VERSION}
- Patch file: $(basename "${PATCH_PATH}")

## Highlights
- TODO

## Validation
- Built with \`Scripts/Build/build_rom.sh ${VERSION}\`
- Overlap check: \`python3 Scripts/Build/check_zscream_overlap.py\`
- Smoke / regression notes: TODO

## Known Issues
- TODO

## Tester Notes
- Apply the BPS patch to your own compatible base ROM.
- Use the patched ROM for emulator testing only.
- If you need a portable save for another emulator, export SRAM separately.
EOF
fi

echo "[beta-patch] Wrote:"
echo "  ${PATCH_PATH}"
echo "  ${MANIFEST_PATH}"
echo "  ${NOTES_PATH}"
