#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: agent_workflow_start.sh [--rom <path>] [--yaze <path>] [--api-port <port>] [--grpc-port <port>]\n                               [--wait-grpc <secs>] [--generate-states [--state <id>]]\n                               [--export-fast --symbols-src <path>] [--no-export]

Starts:
  - yaze in --server mode (gRPC + HTTP)
  - yaze-mcp server
  - mesen2-mcp server
Optionally exports Mesen2 symbols (.mlb) before launch.

Defaults:
  ROM:   <repo>/Roms/oos168.sfc
  YAZE:  ~/src/hobby/yaze/build_ai/bin/Debug/yaze.app/Contents/MacOS/yaze
  API:   8081
  gRPC:  50052
  wait:  60s

Env overrides:
  YAZE_BIN, YAZE_MCP_PYTHON, MESEN2_MCP_PYTHON
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ROM_DEFAULT="${REPO_ROOT}/Roms/oos168.sfc"
YAZE_DEFAULT="${YAZE_BIN:-$HOME/src/hobby/yaze/build_ai/bin/Debug/yaze.app/Contents/MacOS/yaze}"
API_PORT_DEFAULT=8081
GRPC_PORT_DEFAULT=50052
WAIT_GRPC_DEFAULT=60
LOG_FILE="/tmp/oos_agent_workflow.log"

ROM_PATH="$ROM_DEFAULT"
YAZE_BIN_PATH="$YAZE_DEFAULT"
API_PORT="$API_PORT_DEFAULT"
GRPC_PORT="$GRPC_PORT_DEFAULT"
WAIT_GRPC="$WAIT_GRPC_DEFAULT"
GENERATE_STATES=0
STATE_ID=""
EXPORT_SYMBOLS=1
EXPORT_FAST=0
SYMBOLS_SRC=""

: > "$LOG_FILE"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rom)
      ROM_PATH="$2"
      shift 2
      ;;
    --yaze)
      YAZE_BIN_PATH="$2"
      shift 2
      ;;
    --api-port)
      API_PORT="$2"
      shift 2
      ;;
    --grpc-port)
      GRPC_PORT="$2"
      shift 2
      ;;
    --wait-grpc)
      WAIT_GRPC="$2"
      shift 2
      ;;
    --generate-states)
      GENERATE_STATES=1
      shift
      ;;
    --export-fast)
      EXPORT_FAST=1
      shift
      ;;
    --symbols-src)
      SYMBOLS_SRC="$2"
      shift 2
      ;;
    --state)
      STATE_ID="$2"
      shift 2
      ;;
    --no-export)
      EXPORT_SYMBOLS=0
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

log() {
  echo "[agent-workflow] $*" | tee -a "$LOG_FILE"
}

wait_for_port() {
  local port="$1"
  local timeout="$2"
  local start
  start=$(date +%s)
  while true; do
    if command -v nc >/dev/null 2>&1; then
      if nc -z 127.0.0.1 "$port" >/dev/null 2>&1; then
        return 0
      fi
    else
      if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
        return 0
      fi
    fi
    if (( $(date +%s) - start >= timeout )); then
      return 1
    fi
    log "Waiting for gRPC on :$port..."
    sleep 5
  done
}

if [[ ! -f "$ROM_PATH" ]]; then
  echo "ROM not found: $ROM_PATH" >&2
  exit 1
fi

if [[ ! -x "$YAZE_BIN_PATH" ]]; then
  echo "yaze binary not found or not executable: $YAZE_BIN_PATH" >&2
  exit 1
fi

if [[ $EXPORT_SYMBOLS -eq 1 ]]; then
  SYMBOL_PATH="${ROM_PATH}.mlb"
  log "Exporting Mesen2 symbols -> $SYMBOL_PATH"
  if [[ "$EXPORT_FAST" -eq 1 ]]; then
    if [[ -z "$SYMBOLS_SRC" ]]; then
      log "Missing --symbols-src for fast export"
      exit 1
    fi
    if [[ -d "$SYMBOLS_SRC" ]]; then
      "$YAZE_BIN_PATH" --export_symbols_fast --load_asar_symbols "$SYMBOLS_SRC" \
        --export_symbols "$SYMBOL_PATH" --symbol_format mesen
    else
      "$YAZE_BIN_PATH" --export_symbols_fast --load_symbols "$SYMBOLS_SRC" \
        --export_symbols "$SYMBOL_PATH" --symbol_format mesen
    fi
  else
    "$YAZE_BIN_PATH" --headless --rom_file "$ROM_PATH" --export_symbols "$SYMBOL_PATH" --symbol_format mesen
  fi
fi

PIDS_FILE="/tmp/oos_agent_workflow.pids"
: > "$PIDS_FILE"

start_bg() {
  local name="$1"
  shift
  log "Starting ${name}: $*"
  "$@" &
  local pid=$!
  echo "$pid" >> "$PIDS_FILE"
  log "  PID: $pid"
}

# Start yaze server
start_bg "yaze" "$YAZE_BIN_PATH" --server --api_port "$API_PORT" --test_harness_port "$GRPC_PORT" --rom_file "$ROM_PATH"

if [[ "$WAIT_GRPC" -gt 0 ]]; then
  if wait_for_port "$GRPC_PORT" "$WAIT_GRPC"; then
    log "gRPC ready on :$GRPC_PORT"
  else
    log "gRPC not ready after ${WAIT_GRPC}s"
    if [[ "$GENERATE_STATES" -eq 1 ]]; then
      log "Aborting state generation (gRPC not ready)"
      exit 1
    fi
  fi
fi

if [[ "$GENERATE_STATES" -eq 1 ]]; then
  log "Generating yaze-mcp state library..."
  if [[ -n "$STATE_ID" ]]; then
    log "  State: $STATE_ID"
    (cd /Users/scawful/src/tools/yaze-mcp && python3 generate_test_states.py --rom "$ROM_PATH" --state "$STATE_ID")
  else
    log "  Mode: --all"
    (cd /Users/scawful/src/tools/yaze-mcp && python3 generate_test_states.py --rom "$ROM_PATH" --all)
  fi
fi

# Start yaze-mcp
YAZE_MCP_PYTHON_BIN="${YAZE_MCP_PYTHON:-python3}"
start_bg "yaze-mcp" bash -lc "cd /Users/scawful/src/tools/yaze-mcp && \"$YAZE_MCP_PYTHON_BIN\" -m server"

# Start mesen2-mcp
MESEN2_MCP_PYTHON_BIN="${MESEN2_MCP_PYTHON:-python3}"
start_bg "mesen2-mcp" bash -lc "cd /Users/scawful/src/tools/mesen2-mcp && \"$MESEN2_MCP_PYTHON_BIN\" -m mesen2_mcp.server"

cat <<EOF

All processes started. PIDs stored in: $PIDS_FILE
Workflow log: $LOG_FILE
Stop command:
  kill \$(cat "$PIDS_FILE")
EOF
