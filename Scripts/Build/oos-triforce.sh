#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Oracle finish-line action runner.

Usage:
  Scripts/oos-triforce.sh status-json [--pretty]
  Scripts/oos-triforce.sh continue-play
  Scripts/oos-triforce.sh notify
  Scripts/oos-triforce.sh quick-patch
  Scripts/oos-triforce.sh verify-patch
  Scripts/oos-triforce.sh patch-and-play
  Scripts/oos-triforce.sh transition-tests

The "continue-play" and "notify" actions follow the current finish-line focus
from Scripts/oos_status.py.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

status_json() {
  python3 "${ROOT_DIR}/Scripts/oos_status.py" "$@"
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
        ["python3", str(root / "scripts" / "oos_status.py")],
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
  (cd "${ROOT_DIR}" && ./Scripts/oos-quick.sh)
}

verify_patch() {
  (cd "${ROOT_DIR}" && ./Scripts/oos-verify.sh)
}

patch_and_play() {
  verify_patch
  run_focus_command
}

transition_tests() {
  (cd "${ROOT_DIR}" && ./Scripts/Validate/run_regression_tests.sh regression --tag transition -q --fail-fast)
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
  *)
    echo "Unknown action: ${action}" >&2
    usage >&2
    exit 1
    ;;
esac
