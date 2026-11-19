#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: Scripts/Build/beta_patch.sh [version] [options]

Build and package a verified Discord Feature Beta BPS release bundle against
canonical Vanilla US ALTTP 1.0 using Scripts/Build/package_beta_bps.py (isolated
rev5 authoring_bundle_build.py + static gates + flips round-trip verification +
3-slot showcase .srm + release manifest + Discord draft).

Options:
  --label LABEL     Release label (default: oos<version>-beta-<YYYYMMDD_HHMMSS>)
  --out-dir DIR     Output directory (default: build/releases)
  --skip-build      Package an existing ROM (--rom or Roms/oos<version>x.sfc)
                    instead of running an isolated rev5 authoring build first
  --rom PATH        Explicit already-built ROM path (implies --skip-build)
  --symbols PATH    Explicit .sym path for check_zscream_overlap.py
  --vanilla PATH    Canonical vanilla US ALTTP 1.0 .sfc (default: OOS_VANILLA_ROM
                    or ~/src/hobby/roms/Legend of Zelda, The - A Link to the Past (USA).sfc)
  --project PATH    Yaze .yazeproj/project.yaze path for isolated rev5 build
  --enable CSV      Override comma-separated beta feature flags to enable
  --disable CSV     Comma-separated feature flags to disable
  --flips PATH      Explicit path to flips binary
  --notes PATH      Also copy generated Discord release draft to PATH (legacy compat)
  -h, --help        Show this help

Examples:
  Scripts/Build/beta_patch.sh --label v0.9.0-beta1
  Scripts/Build/beta_patch.sh 168 --out-dir /tmp/oos-release
  Scripts/Build/beta_patch.sh 168 --rom /tmp/oos168x.sfc --label dryrun --out-dir /tmp/out
EOF
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACKAGER="${ROOT_DIR}/Scripts/Build/package_beta_bps.py"

VERSION="${OOS_BUILD_VERSION:-168}"
OUT_DIR="${ROOT_DIR}/build/releases"
SKIP_BUILD=0
NOTES_PATH=""
LABEL=""
ROM_PATH=""
SYMBOLS_PATH=""
VANILLA_PATH=""
PROJECT_PATH=""
ENABLE_FLAGS=""
DISABLE_FLAGS=""
FLIPS_PATH=""

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
    --label)
      LABEL="$2"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    --rom)
      ROM_PATH="$2"
      SKIP_BUILD=1
      shift 2
      ;;
    --symbols)
      SYMBOLS_PATH="$2"
      shift 2
      ;;
    --vanilla)
      VANILLA_PATH="$2"
      shift 2
      ;;
    --project)
      PROJECT_PATH="$2"
      shift 2
      ;;
    --enable)
      ENABLE_FLAGS="$2"
      shift 2
      ;;
    --disable)
      DISABLE_FLAGS="$2"
      shift 2
      ;;
    --flips)
      FLIPS_PATH="$2"
      shift 2
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

if [[ -z "${LABEL}" ]]; then
  STAMP="$(date +%Y%m%d_%H%M%S)"
  LABEL="oos${VERSION}-beta-${STAMP}"
fi

CMD=(
  python3 "${PACKAGER}"
  --label "${LABEL}"
  --version "${VERSION}"
  --out-dir "${OUT_DIR}"
)

if [[ "${SKIP_BUILD}" == "1" ]]; then
  if [[ -z "${ROM_PATH}" ]]; then
    ROM_PATH="${ROOT_DIR}/Roms/oos${VERSION}x.sfc"
  fi
  CMD+=(--rom "${ROM_PATH}")
fi

if [[ -n "${SYMBOLS_PATH}" ]]; then
  CMD+=(--symbols "${SYMBOLS_PATH}")
fi
if [[ -n "${VANILLA_PATH}" ]]; then
  CMD+=(--vanilla "${VANILLA_PATH}")
fi
if [[ -n "${PROJECT_PATH}" ]]; then
  CMD+=(--project "${PROJECT_PATH}")
fi
if [[ -n "${ENABLE_FLAGS}" ]]; then
  CMD+=(--enable "${ENABLE_FLAGS}")
fi
if [[ -n "${DISABLE_FLAGS}" ]]; then
  CMD+=(--disable "${DISABLE_FLAGS}")
fi
if [[ -n "${FLIPS_PATH}" ]]; then
  CMD+=(--flips "${FLIPS_PATH}")
fi

"${CMD[@]}"

if [[ -n "${NOTES_PATH}" ]]; then
  DRAFT_SRC="${OUT_DIR}/oracle-of-secrets-${LABEL}-discord.md"
  if [[ -f "${DRAFT_SRC}" && "${NOTES_PATH}" != "${DRAFT_SRC}" ]]; then
    mkdir -p "$(dirname "${NOTES_PATH}")"
    cp -f "${DRAFT_SRC}" "${NOTES_PATH}"
    echo "[beta-patch] Copied release draft to ${NOTES_PATH}"
  fi
fi
