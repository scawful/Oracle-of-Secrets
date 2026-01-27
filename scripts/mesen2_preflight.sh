#!/usr/bin/env bash

# Lightweight preflight: rebuild ROM/Mesen2 if stale.

set -euo pipefail

ROOT_DIR=""
ROM_PATH=""
ROM_SOURCE=""
ROM_VERSION=""
ROM_BUILD_SCRIPT=""
MESEN2_REPO="${MESEN2_REPO:-$HOME/src/hobby/mesen2-oos}"
MESEN2_APP="${MESEN2_APP:-/Applications/Mesen2 OOS.app}"
MESEN2_BUILD_SCRIPT=""
REBUILD_DIRTY=0
STRICT=0
SKIP_ROM=0
SKIP_MESEN2=0

usage() {
  cat <<'EOF'
Mesen2 preflight (rebuild ROM/Mesen2 if stale)

USAGE:
  scripts/mesen2_preflight.sh [options]

OPTIONS:
  --root <dir>        Oracle-of-Secrets repo root (default: script parent)
  --rom <path>        Patched ROM path (default: Roms/oos168x.sfc)
  --rom-source <path> Dev/edit ROM path (default: Roms/oos168_test2.sfc)
  --rom-version <n>   ROM version for build script (default: inferred from ROM name)
  --rom-build <path>  ROM build script (default: scripts/build_rom.sh)
  --mesen2-repo <dir> Mesen2 fork repo (default: ~/src/hobby/mesen2-oos)
  --mesen2-app <path> Mesen2 app bundle (default: /Applications/Mesen2 OOS.app)
  --mesen2-build <p>  Mesen2 build script (optional)
  --rebuild-dirty     Rebuild Mesen2 if repo is dirty
  --no-rom            Skip ROM preflight
  --no-mesen2         Skip Mesen2 preflight
  --strict            Exit non-zero on warnings
  -h, --help          Show help
EOF
}

log() {
  printf '%s\n' "$1"
}

warn() {
  printf 'WARN: %s\n' "$1"
}

err() {
  printf 'ERROR: %s\n' "$1" >&2
}

mtime() {
  local path="$1"
  if [[ "$(uname)" == "Darwin" ]]; then
    stat -f %m "$path" 2>/dev/null || echo 0
  else
    stat -c %Y "$path" 2>/dev/null || echo 0
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT_DIR="$2"
      shift 2
      ;;
    --rom)
      ROM_PATH="$2"
      shift 2
      ;;
    --rom-source)
      ROM_SOURCE="$2"
      shift 2
      ;;
    --rom-version)
      ROM_VERSION="$2"
      shift 2
      ;;
    --rom-build)
      ROM_BUILD_SCRIPT="$2"
      shift 2
      ;;
    --mesen2-repo)
      MESEN2_REPO="$2"
      shift 2
      ;;
    --mesen2-app)
      MESEN2_APP="$2"
      shift 2
      ;;
    --mesen2-build)
      MESEN2_BUILD_SCRIPT="$2"
      shift 2
      ;;
    --rebuild-dirty)
      REBUILD_DIRTY=1
      shift
      ;;
    --no-rom)
      SKIP_ROM=1
      shift
      ;;
    --no-mesen2)
      SKIP_MESEN2=1
      shift
      ;;
    --strict)
      STRICT=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      err "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$ROOT_DIR" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

if [[ -z "$ROM_PATH" ]]; then
  ROM_PATH="${ROOT_DIR}/Roms/oos168x.sfc"
fi
if [[ -z "$ROM_SOURCE" ]]; then
  ROM_SOURCE="${ROOT_DIR}/Roms/oos168_test2.sfc"
fi
if [[ -z "$ROM_BUILD_SCRIPT" ]]; then
  ROM_BUILD_SCRIPT="${ROOT_DIR}/scripts/build_rom.sh"
fi

if [[ -z "$ROM_VERSION" ]]; then
  rom_base="$(basename "$ROM_PATH")"
  if [[ "$rom_base" =~ oos([0-9]+)x\.sfc ]]; then
    ROM_VERSION="${BASH_REMATCH[1]}"
  else
    ROM_VERSION="168"
  fi
fi

rom_warn=0
if [[ $SKIP_ROM -eq 0 ]]; then
  if [[ ! -f "$ROM_PATH" ]]; then
    warn "Patched ROM missing: $ROM_PATH"
    rom_warn=1
  fi
  if [[ -f "$ROM_SOURCE" ]]; then
    if [[ $(mtime "$ROM_SOURCE") -gt $(mtime "$ROM_PATH") ]]; then
      warn "Patched ROM older than dev ROM: $ROM_PATH"
      rom_warn=1
    fi
  fi
  if [[ $rom_warn -ne 0 ]]; then
    if [[ -x "$ROM_BUILD_SCRIPT" ]]; then
      log "Rebuilding ROM (version $ROM_VERSION)..."
      "$ROM_BUILD_SCRIPT" "$ROM_VERSION"
      rom_warn=0
    else
      warn "ROM build script not executable: $ROM_BUILD_SCRIPT"
    fi
  fi
fi

mesen_warn=0
if [[ $SKIP_MESEN2 -eq 0 ]]; then
  if [[ ! -d "$MESEN2_REPO/.git" ]]; then
    warn "Mesen2 repo not found: $MESEN2_REPO"
    mesen_warn=1
  else
    head_time="$(git -C "$MESEN2_REPO" log -1 --format=%ct 2>/dev/null || echo 0)"
    dirty_count="$(git -C "$MESEN2_REPO" status --porcelain 2>/dev/null | wc -l | tr -d '[:space:]')"
    mesen_bin="${MESEN2_APP}/Contents/MacOS/Mesen"
    if [[ ! -x "$mesen_bin" ]]; then
      warn "Mesen2 binary missing: $mesen_bin"
      mesen_warn=1
    else
      bin_time="$(mtime "$mesen_bin")"
      if [[ "$bin_time" -lt "$head_time" ]]; then
        warn "Mesen2 binary is older than repo HEAD."
        mesen_warn=1
      fi
    fi
    if [[ "$dirty_count" -gt 0 ]]; then
      warn "Mesen2 repo dirty (${dirty_count} changes)."
      if [[ $REBUILD_DIRTY -eq 1 ]]; then
        mesen_warn=1
      fi
    fi
  fi

  if [[ $mesen_warn -ne 0 ]]; then
    if [[ -z "$MESEN2_BUILD_SCRIPT" ]]; then
      if [[ -x "${MESEN2_REPO}/tools/build_mesen2_oos_cmake.sh" ]]; then
        MESEN2_BUILD_SCRIPT="${MESEN2_REPO}/tools/build_mesen2_oos_cmake.sh"
      elif [[ -x "${MESEN2_REPO}/build_mesen2_oos.sh" ]]; then
        MESEN2_BUILD_SCRIPT="${MESEN2_REPO}/build_mesen2_oos.sh"
      elif [[ -f "${MESEN2_REPO}/makefile" ]]; then
        MESEN2_BUILD_SCRIPT="make"
      elif [[ -f "${MESEN2_REPO}/Makefile" ]]; then
        MESEN2_BUILD_SCRIPT="make"
      fi
    fi
    log "Rebuilding Mesen2..."
    if [[ "$MESEN2_BUILD_SCRIPT" == "make" ]]; then
      make -C "$MESEN2_REPO"
      mesen_warn=0
    elif [[ -n "$MESEN2_BUILD_SCRIPT" && -x "$MESEN2_BUILD_SCRIPT" ]]; then
      "$MESEN2_BUILD_SCRIPT"
      mesen_warn=0
    else
      warn "No Mesen2 build script available."
    fi
  fi
fi

if [[ $STRICT -eq 1 ]]; then
  if [[ $rom_warn -ne 0 || $mesen_warn -ne 0 ]]; then
    exit 2
  fi
fi

log "Preflight OK."
