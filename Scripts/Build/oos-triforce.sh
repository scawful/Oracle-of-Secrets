#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Oracle finish-line action runner.

Usage:
  Scripts/Build/oos-triforce.sh status-json [--pretty]
  Scripts/Build/oos-triforce.sh continue-play
  Scripts/Build/oos-triforce.sh notify
  Scripts/Build/oos-triforce.sh quick-patch
  Scripts/Build/oos-triforce.sh verify-patch
  Scripts/Build/oos-triforce.sh patch-and-play
  Scripts/Build/oos-triforce.sh transition-tests
  Scripts/Build/oos-triforce.sh launch [stable|test]

The "continue-play" and "notify" actions follow the current finish-line focus
from Scripts/Debug/oos_status.py.

"launch stable" opens the highest Roms/oosNNNx.sfc in the Mesen2 instance
oos-<user>-debug. "launch test" opens the newest Roms/TestBuilds/*/oosNNNx.sfc
in the instance oos-<user>-test, which keeps its own saves. If the instance is
already running, it loads the ROM instead.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

status_json() {
  python3 "${ROOT_DIR}/Scripts/Debug/oos_status.py" "$@"
}

finish_field() {
  local expression="$1"
  python3 - "$expression" "${ROOT_DIR}" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

expression = sys.argv[1]
root = Path(sys.argv[2])
payload = json.loads(
    subprocess.check_output(
        ["python3", str(root / "Scripts" / "Debug" / "oos_status.py")],
        cwd=root,
        text=True,
    )
)

parts = expression.split(".")
value = payload
for part in parts:
    if isinstance(value, dict):
        value = value.get(part)
    else:
        value = None
        break

if value is None:
    sys.exit(1)
if isinstance(value, (dict, list)):
    print(json.dumps(value))
else:
    print(value)
PY
}

notify() {
  local title subtitle message execute_cmd
  title="$(finish_field "finish_line.notification.title")"
  subtitle="$(finish_field "finish_line.notification.subtitle")"
  message="$(finish_field "finish_line.notification.message")"
  execute_cmd="${HOME}/src/config/dotfiles/bin/oos-workbench continue-play"

  if command -v terminal-notifier >/dev/null 2>&1; then
    terminal-notifier \
      -group "oracle-triforce" \
      -title "${title}" \
      -subtitle "${subtitle}" \
      -message "${message}" \
      -execute "${execute_cmd}" >/dev/null 2>&1 || true
  else
    osascript -e "display notification $(printf '%q' "${message}") with title $(printf '%q' "${title}") subtitle $(printf '%q' "${subtitle}")" >/dev/null 2>&1 || true
  fi
}

run_focus_command() {
  local command
  command="$(finish_field "finish_line.focus.command")"
  if [[ -z "${command}" ]]; then
    echo "No finish-line focus command available." >&2
    exit 1
  fi
  (cd "${ROOT_DIR}" && bash -lc "${command}")
}

quick_patch() {
  (cd "${ROOT_DIR}" && ./Scripts/Build/oos-quick.sh)
}

verify_patch() {
  (cd "${ROOT_DIR}" && ./Scripts/Build/oos-verify.sh)
}

patch_and_play() {
  verify_patch
  run_focus_command
}

transition_tests() {
  (cd "${ROOT_DIR}" && ./Scripts/Validate/run_regression_tests.sh regression --tag transition -q --fail-fast)
}

stable_rom() {
  local best="" best_version=-1 path name version
  for path in "${ROOT_DIR}"/Roms/oos*x.sfc; do
    [[ -f "${path}" ]] || continue
    name="${path##*/}"
    version="${name#oos}"
    version="${version%x.sfc}"
    [[ "${version}" =~ ^[0-9]+$ ]] || continue
    if (( version > best_version )); then
      best_version="${version}"
      best="${path}"
    fi
  done
  printf '%s' "${best}"
}

newest_test_rom() {
  local newest="" path
  for path in "${ROOT_DIR}"/Roms/TestBuilds/*/oos*x.sfc; do
    [[ -f "${path}" ]] || continue
    if [[ -z "${newest}" || "${path}" -nt "${newest}" ]]; then
      newest="${path}"
    fi
  done
  printf '%s' "${newest}"
}

socket_live() {
  [[ -S "$1" ]] || return 1
  python3 - "$1" <<'PY'
import socket
import sys

client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.settimeout(0.5)
try:
    client.connect(sys.argv[1])
except OSError:
    sys.exit(1)
finally:
    client.close()
PY
}

launch_rom() {
  local channel="${1:-stable}"
  local owner="${USER:-scawful}"
  local rom instance socket force=""
  case "${channel}" in
    stable)
      rom="$(stable_rom)"
      instance="oos-${owner}-debug"
      ;;
    test)
      rom="$(newest_test_rom)"
      instance="oos-${owner}-test"
      ;;
    *)
      echo "Unknown launch channel: ${channel} (use stable or test)" >&2
      exit 1
      ;;
  esac
  if [[ -z "${rom}" ]]; then
    echo "No ${channel} ROM found under ${ROOT_DIR}/Roms." >&2
    exit 1
  fi

  socket="/tmp/mesen2-${instance}.sock"
  if socket_live "${socket}"; then
    python3 "${ROOT_DIR}/Scripts/Mesen2/mesen2_client.py" --instance "${instance}" rom-load "${rom}"
    return
  fi
  if [[ -S "${socket}" ]]; then
    # Stale socket from a closed instance: reuse the same name and saves.
    force="--socket-force"
  fi
  "${ROOT_DIR}/Scripts/Mesen2/mesen2_launch_instance.sh" \
    --instance "${instance}" \
    --owner "${owner}" \
    --source manual \
    --rom "${rom}" \
    ${force:+"${force}"}
}

action="${1:-status-json}"
shift || true

case "${action}" in
  -h|--help|help)
    usage
    ;;
  status-json)
    status_json "$@"
    ;;
  continue-play)
    run_focus_command
    ;;
  notify)
    notify
    ;;
  quick-patch)
    quick_patch
    ;;
  verify-patch)
    verify_patch
    ;;
  patch-and-play)
    patch_and_play
    ;;
  transition-tests)
    transition_tests
    ;;
  launch)
    launch_rom "$@"
    ;;
  *)
    echo "Unknown action: ${action}" >&2
    usage >&2
    exit 1
    ;;
esac
