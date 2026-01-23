#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}"
shift || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ROM_DEFAULT="${REPO_ROOT}/Roms/oos168x.sfc"
API_PORT_DEFAULT="${YAZE_API_PORT:-8081}"
GRPC_PORT_DEFAULT="${YAZE_GRPC_PORT:-50052}"
GUI_API_PORT_DEFAULT="${YAZE_GUI_API_PORT:-8082}"
GUI_GRPC_PORT_DEFAULT="${YAZE_GUI_GRPC_PORT:-50053}"

PID_FILE="${YAZE_PID_FILE:-/tmp/oos_yaze_service.pid}"
GUI_PID_FILE="${YAZE_GUI_PID_FILE:-/tmp/oos_yaze_gui.pid}"
LOG_FILE="${YAZE_LOG_FILE:-/tmp/oos_yaze_service.log}"
GUI_LOG_FILE="${YAZE_GUI_LOG_FILE:-/tmp/oos_yaze_gui.log}"

usage() {
  cat <<'EOF'
Usage: yaze_service.sh <action> [options]

Actions:
  start | stop | restart | status
  gui-start | gui-stop | gui-toggle
  sync-nightly

Options:
  --rom PATH         ROM path (default: Roms/oos168x.sfc)
  --api-port PORT    HTTP API port (default: 8081)
  --grpc-port PORT   gRPC port (default: 50052)
  --gui-api PORT     GUI HTTP API port (default: 8082)
  --gui-grpc PORT    GUI gRPC port (default: 50053)
  --bin PATH         Yaze binary (server)
  --gui-bin PATH     Yaze binary (GUI)

Env overrides:
  YAZE_BIN, YAZE_GUI_BIN, YAZE_API_PORT, YAZE_GRPC_PORT,
  YAZE_GUI_API_PORT, YAZE_GUI_GRPC_PORT, YAZE_PID_FILE, YAZE_GUI_PID_FILE
EOF
}

resolve_bin() {
  local override="$1"
  if [[ -n "$override" ]]; then
    echo "$override"
    return
  fi
  if command -v yaze-nightly >/dev/null 2>&1; then
    echo "yaze-nightly"
    return
  fi
  local fallback1="$HOME/src/hobby/yaze/build_ai/bin/Debug/yaze.app/Contents/MacOS/yaze"
  local fallback2="$HOME/src/hobby/yaze/build/bin/yaze"
  if [[ -x "$fallback1" ]]; then
    echo "$fallback1"
    return
  fi
  if [[ -x "$fallback2" ]]; then
    echo "$fallback2"
    return
  fi
  echo ""
}

ROM_PATH="$ROM_DEFAULT"
API_PORT="$API_PORT_DEFAULT"
GRPC_PORT="$GRPC_PORT_DEFAULT"
GUI_API_PORT="$GUI_API_PORT_DEFAULT"
GUI_GRPC_PORT="$GUI_GRPC_PORT_DEFAULT"
YAZE_BIN_PATH=""
YAZE_GUI_BIN_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rom)
      ROM_PATH="$2"; shift 2 ;;
    --api-port)
      API_PORT="$2"; shift 2 ;;
    --grpc-port)
      GRPC_PORT="$2"; shift 2 ;;
    --gui-api)
      GUI_API_PORT="$2"; shift 2 ;;
    --gui-grpc)
      GUI_GRPC_PORT="$2"; shift 2 ;;
    --bin)
      YAZE_BIN_PATH="$2"; shift 2 ;;
    --gui-bin)
      YAZE_GUI_BIN_PATH="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1 ;;
  esac
done

ensure_pid_stopped() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" || true)"
    if [[ -n "$pid" && -n "$(ps -p "$pid" -o pid= 2>/dev/null)" ]]; then
      return 1
    fi
    rm -f "$pid_file"
  fi
  return 0
}

start_server() {
  local bin
  bin="$(resolve_bin "${YAZE_BIN_PATH:-${YAZE_BIN:-}}")"
  if [[ -z "$bin" ]]; then
    echo "yaze binary not found (set YAZE_BIN or install nightly)" >&2
    exit 1
  fi
  if [[ ! -f "$ROM_PATH" ]]; then
    echo "ROM not found: $ROM_PATH" >&2
    exit 1
  fi
  if ! ensure_pid_stopped "$PID_FILE"; then
    echo "yaze server already running (pid $(cat "$PID_FILE"))" >&2
    return
  fi
  : > "$LOG_FILE"
  echo "[yaze-service] Starting: $bin --server --api_port $API_PORT --test_harness_port $GRPC_PORT --rom_file $ROM_PATH" | tee -a "$LOG_FILE"
  "$bin" --server --api_port "$API_PORT" --test_harness_port "$GRPC_PORT" --rom_file "$ROM_PATH" >>"$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  echo "[yaze-service] PID $(cat "$PID_FILE")" | tee -a "$LOG_FILE"
}

stop_server() {
  if [[ ! -f "$PID_FILE" ]]; then
    echo "yaze server not running (no pid file)" >&2
    return
  fi
  local pid
  pid="$(cat "$PID_FILE" || true)"
  if [[ -n "$pid" ]]; then
    kill "$pid" 2>/dev/null || true
    sleep 0.5
    if ps -p "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
  rm -f "$PID_FILE"
  echo "[yaze-service] Stopped"
}

start_gui() {
  local bin
  bin="$(resolve_bin "${YAZE_GUI_BIN_PATH:-${YAZE_GUI_BIN:-}}")"
  if [[ -z "$bin" ]]; then
    echo "yaze GUI binary not found (set YAZE_GUI_BIN or install nightly)" >&2
    exit 1
  fi
  if [[ ! -f "$ROM_PATH" ]]; then
    echo "ROM not found: $ROM_PATH" >&2
    exit 1
  fi
  if ! ensure_pid_stopped "$GUI_PID_FILE"; then
    echo "yaze GUI already running (pid $(cat "$GUI_PID_FILE"))" >&2
    return
  fi
  : > "$GUI_LOG_FILE"
  echo "[yaze-gui] Starting: $bin --enable_api --enable_test_harness --api_port $GUI_API_PORT --test_harness_port $GUI_GRPC_PORT --rom_file $ROM_PATH" | tee -a "$GUI_LOG_FILE"
  "$bin" --enable_api --enable_test_harness --api_port "$GUI_API_PORT" --test_harness_port "$GUI_GRPC_PORT" \
    --rom_file "$ROM_PATH" --startup_welcome hide --startup_dashboard hide --startup_sidebar hide >>"$GUI_LOG_FILE" 2>&1 &
  echo $! > "$GUI_PID_FILE"
  echo "[yaze-gui] PID $(cat "$GUI_PID_FILE")" | tee -a "$GUI_LOG_FILE"
}

stop_gui() {
  if [[ ! -f "$GUI_PID_FILE" ]]; then
    echo "yaze GUI not running (no pid file)" >&2
    return
  fi
  local pid
  pid="$(cat "$GUI_PID_FILE" || true)"
  if [[ -n "$pid" ]]; then
    kill "$pid" 2>/dev/null || true
    sleep 0.5
    if ps -p "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
  rm -f "$GUI_PID_FILE"
  echo "[yaze-gui] Stopped"
}

status_server() {
  local status="stopped"
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE" || true)"
    if [[ -n "$pid" && -n "$(ps -p "$pid" -o pid= 2>/dev/null)" ]]; then
      status="running"
    fi
  fi
  echo "yaze server: $status (api:$API_PORT grpc:$GRPC_PORT)"
  if command -v curl >/dev/null 2>&1; then
    curl -s "http://127.0.0.1:${API_PORT}/api/v1/health" || true
  fi
}

status_gui() {
  local status="stopped"
  if [[ -f "$GUI_PID_FILE" ]]; then
    local pid
    pid="$(cat "$GUI_PID_FILE" || true)"
    if [[ -n "$pid" && -n "$(ps -p "$pid" -o pid= 2>/dev/null)" ]]; then
      status="running"
    fi
  fi
  echo "yaze gui: $status (api:$GUI_API_PORT grpc:$GUI_GRPC_PORT)"
}

sync_nightly() {
  local installer="$HOME/src/hobby/yaze/scripts/install-nightly.sh"
  if [[ ! -x "$installer" ]]; then
    echo "Nightly installer not found: $installer" >&2
    exit 1
  fi
  "$installer"
}

case "$ACTION" in
  start)
    start_server
    ;;
  stop)
    stop_server
    ;;
  restart)
    stop_server
    start_server
    ;;
  status)
    status_server
    status_gui
    ;;
  gui-start)
    start_gui
    ;;
  gui-stop)
    stop_gui
    ;;
  gui-toggle)
    if [[ -f "$GUI_PID_FILE" ]]; then
      stop_gui
    else
      start_gui
    fi
    ;;
  sync-nightly)
    sync_nightly
    ;;
  *)
    usage
    exit 1
    ;;
 esac
