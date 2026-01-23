#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Manage a LaunchAgent for mesen_socket_server.py (hub).

Usage: mesen_hub_launchagent.sh <install|uninstall|start|stop|restart|status|print>

Options:
  --profile NAME   Profile name (default: default)
  --tcp PORT       TCP port for Mesen2 (default: 5050)
  --http PORT      HTTP port for agents (default: 8080)

Env:
  MESEN_PROFILE    Default profile name
  MESEN_TCP_PORT   Default TCP port
  MESEN_HTTP_PORT  Default HTTP port
  MESEN_HUB_ID     Optional hub identifier (defaults to profile)
USAGE
}

ACTION="${1:-status}"
if [[ "${ACTION}" != "status" && "${ACTION}" != "print" ]]; then
  shift || true
fi

PROFILE="${MESEN_PROFILE:-default}"
TCP_PORT="${MESEN_TCP_PORT:-5050}"
HTTP_PORT="${MESEN_HTTP_PORT:-8080}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      PROFILE="${2:-default}"
      shift 2
      ;;
    --tcp)
      TCP_PORT="${2:-5050}"
      shift 2
      ;;
    --http)
      HTTP_PORT="${2:-8080}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LABEL="com.scawful.mesen2-hub.${PROFILE}"
PLIST_PATH="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_PATH="$HOME/Library/Logs/mesen2-hub.${PROFILE}.log"
ERR_PATH="$HOME/Library/Logs/mesen2-hub.${PROFILE}.err.log"
HUB_ID="${MESEN_HUB_ID:-${PROFILE}}"

render_plist() {
  cat <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>${REPO_ROOT}/scripts/mesen_socket_server.py</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MESEN_TCP_HOST</key>
    <string>127.0.0.1</string>
    <key>MESEN_HTTP_HOST</key>
    <string>127.0.0.1</string>
    <key>MESEN_TCP_PORT</key>
    <string>${TCP_PORT}</string>
    <key>MESEN_HTTP_PORT</key>
    <string>${HTTP_PORT}</string>
    <key>MESEN_HUB_ID</key>
    <string>${HUB_ID}</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
  </dict>
  <key>WorkingDirectory</key>
  <string>${REPO_ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_PATH}</string>
  <key>StandardErrorPath</key>
  <string>${ERR_PATH}</string>
</dict>
</plist>
PLIST
}

bootstrap_agent() {
  launchctl bootstrap "gui/${UID}" "${PLIST_PATH}"
}

bootout_agent() {
  launchctl bootout "gui/${UID}" "${PLIST_PATH}" >/dev/null 2>&1 || true
}

case "${ACTION}" in
  install)
    mkdir -p "$(dirname "${PLIST_PATH}")" "$(dirname "${LOG_PATH}")"
    render_plist > "${PLIST_PATH}"
    bootout_agent
    bootstrap_agent
    echo "Installed and started ${LABEL}"
    ;;
  uninstall)
    bootout_agent
    rm -f "${PLIST_PATH}"
    echo "Removed ${LABEL}"
    ;;
  start)
    if [[ ! -f "${PLIST_PATH}" ]]; then
      echo "Missing plist: ${PLIST_PATH}" >&2
      exit 1
    fi
    bootstrap_agent
    echo "Started ${LABEL}"
    ;;
  stop)
    bootout_agent
    echo "Stopped ${LABEL}"
    ;;
  restart)
    if [[ ! -f "${PLIST_PATH}" ]]; then
      echo "Missing plist: ${PLIST_PATH}" >&2
      exit 1
    fi
    bootout_agent
    bootstrap_agent
    echo "Restarted ${LABEL}"
    ;;
  status)
    launchctl print "gui/${UID}/${LABEL}" 2>/dev/null || echo "${LABEL} not loaded"
    ;;
  print)
    render_plist
    ;;
  *)
    usage
    exit 1
    ;;
esac
