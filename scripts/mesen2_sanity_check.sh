#!/usr/bin/env bash

# Lightweight Mesen2 socket/API sanity check for Ralph loops.

set -euo pipefail

ROOT_DIR=""
INSTANCE=""
OWNER=""
ROM_PATH=""
SOCKET_PATH=""
REGISTRY_SCRIPT=""
CHECK_REPO=1
STRICT=0

usage() {
  cat <<'EOF'
Mesen2 sanity check

USAGE:
  scripts/mesen2_sanity_check.sh [options]

OPTIONS:
  --root <dir>       Oracle-of-Secrets repo root (default: script parent)
  --instance <name>  Registry instance name to resolve socket
  --owner <name>     Owner label (optional, for logging)
  --rom <path>       Expected ROM path (optional)
  --socket <path>    Socket path override (optional)
  --registry <path>  Path to mesen2_registry.py (optional)
  --no-repo          Skip Mesen2 repo status check
  --strict           Exit non-zero on warnings (rom mismatch, missing rom)
  -h, --help         Show help
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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT_DIR="$2"
      shift 2
      ;;
    --instance)
      INSTANCE="$2"
      shift 2
      ;;
    --owner)
      OWNER="$2"
      shift 2
      ;;
    --rom)
      ROM_PATH="$2"
      shift 2
      ;;
    --socket)
      SOCKET_PATH="$2"
      shift 2
      ;;
    --registry)
      REGISTRY_SCRIPT="$2"
      shift 2
      ;;
    --no-repo)
      CHECK_REPO=0
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

if [[ -z "$REGISTRY_SCRIPT" ]]; then
  REGISTRY_SCRIPT="${ROOT_DIR}/scripts/mesen2_registry.py"
fi

if [[ $CHECK_REPO -eq 1 ]]; then
  MESEN2_REPO="${MESEN2_REPO:-$HOME/src/hobby/mesen2-oos}"
  if [[ -d "$MESEN2_REPO/.git" ]]; then
    log "Mesen2 repo: $MESEN2_REPO"
    git -C "$MESEN2_REPO" status -sb | head -n 5 || true
    git -C "$MESEN2_REPO" log -1 --oneline || true
  else
    warn "Mesen2 repo not found at $MESEN2_REPO"
    if [[ $STRICT -eq 1 ]]; then
      exit 2
    fi
  fi
fi

if [[ -z "$SOCKET_PATH" && -n "${MESEN2_SOCKET_PATH:-}" ]]; then
  SOCKET_PATH="$MESEN2_SOCKET_PATH"
fi

if [[ -n "$SOCKET_PATH" && ! -S "$SOCKET_PATH" ]]; then
  warn "Socket not found at $SOCKET_PATH"
  SOCKET_PATH=""
fi

if [[ -z "$SOCKET_PATH" && -n "$INSTANCE" && -f "$REGISTRY_SCRIPT" ]]; then
  resolved="$(python3 "$REGISTRY_SCRIPT" resolve --instance "$INSTANCE" 2>/dev/null || true)"
  if [[ -n "$resolved" && -S "$resolved" ]]; then
    SOCKET_PATH="$resolved"
  fi
fi

if [[ -n "$INSTANCE" ]]; then
  export MESEN2_INSTANCE="$INSTANCE"
fi

if [[ -z "$SOCKET_PATH" ]]; then
  if [[ -n "$INSTANCE" ]]; then
    err "No live socket resolved for instance: $INSTANCE"
    exit 2
  else
    newest="$(ls -t /tmp/mesen2-*.sock 2>/dev/null | head -n 1 || true)"
    if [[ -n "$newest" && -S "$newest" ]]; then
      SOCKET_PATH="$newest"
    fi
  fi
fi

if [[ -z "$SOCKET_PATH" ]]; then
  err "No live Mesen2 socket found."
  exit 2
fi

export MESEN2_SOCKET_PATH="$SOCKET_PATH"
log "Socket: $SOCKET_PATH"
if [[ -n "$INSTANCE" ]]; then
  log "Instance: $INSTANCE"
fi
if [[ -n "$OWNER" ]]; then
  log "Owner: $OWNER"
fi

rom_failed=0
if [[ -n "$ROM_PATH" ]]; then
  if [[ ! -f "$ROM_PATH" ]]; then
    warn "Expected ROM missing: $ROM_PATH"
    rom_failed=1
  else
    rom_base="$(basename "$ROM_PATH")"
    log "Expected ROM: $rom_base"
    if [[ -f "$REGISTRY_SCRIPT" ]]; then
      python3 - "$ROM_PATH" "$SOCKET_PATH" "$REGISTRY_SCRIPT" <<'PY' || rom_failed=1
import json
import subprocess
import sys

rom_path, socket_path, registry = sys.argv[1:]
rom_base = rom_path.split("/")[-1]

try:
    out = subprocess.check_output([sys.executable, registry, "scan", "--json"], text=True)
    data = json.loads(out)
except Exception:
    sys.exit(0)

match = None
for entry in data:
    if entry.get("socket") == socket_path:
        match = entry
        break
if not match:
    sys.exit(0)

rom_name = match.get("rom_filename")
if rom_name and rom_name != rom_base:
    print(f"WARN: ROM mismatch (socket rom={rom_name}, expected={rom_base})")
    sys.exit(2)
PY
    fi
  fi
fi

if [[ $rom_failed -ne 0 && $STRICT -eq 1 ]]; then
  exit 2
fi

log "State check..."
python3 "$ROOT_DIR/scripts/mesen2_client.py" state --json >/dev/null

log "Input check..."
python3 "$ROOT_DIR/scripts/mesen2_client.py" press RIGHT --frames 1 >/dev/null

log "Sanity check OK."
