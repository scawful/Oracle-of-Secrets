#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Oracle of Secrets - one-command dev loop

Usage:
  scripts/dev_loop.sh [version] [options]

Options:
  --version N         ROM version (default: 168)
  --asar PATH         Asar binary path (or "z3asm" to use local build)
  --z3asm             Use local z3asm build if available
  --base-rom PATH     Override base ROM (sets OOS_BASE_ROM)
  --reload            Reset Mesen2 after build
  --mesen-sync        Sync MLB symbols into Mesen2 Debug folder
  --no-symbols        Skip symbol emission
  --skip-tests        Skip smoke tests
  --validate          Run hook + sprite validators (non-fatal)
  --annotations       Generate annotations.json (OOS_GENERATE_ANNOTATIONS=1)
  --yaze-restart      Restart yaze service with patched ROM
  --yaze-sync         One-shot yaze<->Mesen2 sync (yaze must be running)
  -h, --help          Show this help

Examples:
  scripts/dev_loop.sh 168 --z3asm --mesen-sync --reload --validate
  scripts/dev_loop.sh --version 168 --asar /usr/local/bin/asar --skip-tests
  scripts/dev_loop.sh 168 --yaze-restart --yaze-sync
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

version=""
asar_bin=""
base_rom=""
reload=0
mesen_sync=0
no_symbols=0
skip_tests=0
validate=0
annotations=0
yaze_restart=0
yaze_sync=0

if [[ $# -gt 0 && "${1}" != "-"* ]]; then
  version="$1"
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      version="$2"; shift 2 ;;
    --asar)
      asar_bin="$2"; shift 2 ;;
    --z3asm)
      asar_bin="z3asm"; shift ;;
    --base-rom)
      base_rom="$2"; shift 2 ;;
    --reload)
      reload=1; shift ;;
    --mesen-sync)
      mesen_sync=1; shift ;;
    --no-symbols)
      no_symbols=1; shift ;;
    --skip-tests)
      skip_tests=1; shift ;;
    --validate)
      validate=1; shift ;;
    --annotations)
      annotations=1; shift ;;
    --yaze-restart)
      yaze_restart=1; shift ;;
    --yaze-sync)
      yaze_sync=1; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1 ;;
  esac
done

version="${version:-168}"

if ! [[ "$version" =~ ^[0-9]+$ ]]; then
  echo "ERROR: version must be numeric (got: $version)" >&2
  exit 1
fi

patched_rom="${ROOT_DIR}/Roms/oos${version}x.sfc"

env_args=()
if [[ -n "$base_rom" ]]; then
  env_args+=("OOS_BASE_ROM=${base_rom}")
fi
if [[ "$validate" -eq 1 ]]; then
  env_args+=("OOS_VALIDATE_ON_BUILD=1")
fi
if [[ "$annotations" -eq 1 ]]; then
  env_args+=("OOS_GENERATE_ANNOTATIONS=1")
fi

build_args=("${version}")
if [[ -n "$asar_bin" ]]; then
  build_args+=("${asar_bin}")
fi
if [[ "$reload" -eq 1 ]]; then
  build_args+=("--reload")
fi
if [[ "$mesen_sync" -eq 1 ]]; then
  build_args+=("--mesen-sync")
fi
if [[ "$no_symbols" -eq 1 ]]; then
  build_args+=("--no-symbols")
fi
if [[ "$skip_tests" -eq 1 ]]; then
  build_args+=("--skip-tests")
fi

echo "[dev-loop] Build: version=${version}"
if [[ ${#env_args[@]} -gt 0 ]]; then
  echo "[dev-loop] Env: ${env_args[*]}"
fi

env "${env_args[@]}" "${ROOT_DIR}/scripts/build_rom.sh" "${build_args[@]}"

if [[ "$yaze_restart" -eq 1 ]]; then
  if [[ -x "${ROOT_DIR}/scripts/yaze_service.sh" ]]; then
    echo "[dev-loop] Restarting yaze service..."
    "${ROOT_DIR}/scripts/yaze_service.sh" restart --rom "${patched_rom}"
  else
    echo "[dev-loop] yaze_service.sh not found; skipping restart." >&2
  fi
fi

if [[ "$yaze_sync" -eq 1 ]]; then
  if [[ -f "${ROOT_DIR}/scripts/yaze_sync.py" ]]; then
    echo "[dev-loop] Running yaze sync (once)..."
    python3 "${ROOT_DIR}/scripts/yaze_sync.py" --once || true
  else
    echo "[dev-loop] yaze_sync.py not found; skipping sync." >&2
  fi
fi

echo "[dev-loop] Done."
