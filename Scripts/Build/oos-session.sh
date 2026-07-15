#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Launch or reuse an isolated Oracle debug instance and jump into a named task.

Usage:
  Scripts/Build/oos-session.sh <task> [options]

Tasks:
  free        Launch/reuse instance only
  maku        Warp to Maku Tree with threshold-test setup
  d4          Load Zora Temple outside seed
  zora        Alias for d4
  d6          Load D6 overworld entrance seed
  d6inside    Load D6 inside entrance seed
  d6cart      Load D6 minecart room seed
  menu        Load menu/debug slot seed
  list        Show task names

Seed source:
  Non-free tasks load from Docs/Debugging/Testing/trusted_state_seeds.json.
  Each mapped ID must be canon + captured_by=human.

Options:
  --instance NAME   Mesen2 instance name (default: oos-<owner>-debug)
  --owner NAME      Owner label (default: $USER)
  --version N       ROM version (default: 168)
  --crystals N      Maku threshold count: 0, 1, 3, 5, or 7 (default: 0)
  -h, --help        Show help

Examples:
  Scripts/Build/oos-session.sh maku --crystals 3
  Scripts/Build/oos-session.sh d6 --instance oos-scawful-debug
  Scripts/Build/oos-session.sh free
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TRUSTED_SEEDS="${ROOT_DIR}/Docs/Debugging/Testing/trusted_state_seeds.json"

task="${1:-}"
if [[ -z "${task}" || "${task}" == "-h" || "${task}" == "--help" ]]; then
  usage
  exit 0
fi
shift || true

owner="${USER:-scawful}"
instance=""
version="168"
maku_crystals="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance)
      instance="$2"
      shift 2
      ;;
    --owner)
      owner="$2"
      shift 2
      ;;
    --version)
      version="$2"
      shift 2
      ;;
    --crystals)
      maku_crystals="$2"
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

if [[ -z "${instance}" ]]; then
  instance="oos-${owner}-debug"
fi

if ! [[ "${version}" =~ ^[0-9]+$ ]]; then
  echo "Version must be numeric: ${version}" >&2
  exit 1
fi

rom_path="${ROOT_DIR}/Roms/oos${version}x.sfc"
if [[ ! -f "${rom_path}" ]]; then
  echo "Patched ROM not found: ${rom_path}" >&2
  exit 1
fi

client() {
  python3 "${ROOT_DIR}/Scripts/Mesen2/mesen2_client.py" --instance "${instance}" "$@"
}

load_trusted_state_for_task() {
  local task_key="$1"
  if [[ ! -f "${TRUSTED_SEEDS}" ]]; then
    echo "Trusted seed config missing: ${TRUSTED_SEEDS}" >&2
    exit 1
  fi

  local state_id
  state_id="$(
    python3 - "${TRUSTED_SEEDS}" "${task_key}" <<'PY'
import json
import sys
from pathlib import Path

cfg = Path(sys.argv[1])
task = sys.argv[2]
data = json.loads(cfg.read_text())
tasks = data.get("tasks", {})
value = tasks.get(task)
if value:
    print(value)
PY
  )"

  if [[ -z "${state_id}" ]]; then
    echo "No trusted seed configured for task '${task_key}' in ${TRUSTED_SEEDS}." >&2
    echo "Capture and promote a state, then set tasks.${task_key} to that state ID." >&2
    echo "Hint: python3 Scripts/Mesen2/mesen2_client.py library --json" >&2
    exit 2
  fi

  local info_json
  info_json="$(client lib-info "${state_id}" --json)"
  INFO_JSON="${info_json}" python3 - "${state_id}" <<'PY'
import json
import os
import sys

state_id = sys.argv[1]
entry = json.loads(os.environ["INFO_JSON"])
status = entry.get("status")
captured_by = entry.get("captured_by")
if status != "canon":
    raise SystemExit(f"State {state_id} rejected: status={status!r} (need 'canon').")
if captured_by != "human":
    raise SystemExit(f"State {state_id} rejected: captured_by={captured_by!r} (need 'human').")
PY

  client lib-load "${state_id}"
}

launch_instance() {
  "${ROOT_DIR}/Scripts/Mesen2/mesen2_launch_instance.sh" \
    --reuse \
    --instance "${instance}" \
    --owner "${owner}" \
    --source manual \
    --rom "${rom_path}" >/dev/null
  client health >/dev/null
}

maku_crystal_value() {
  case "$1" in
    0) printf '0x00' ;;
    1) printf '0x01' ;;
    3) printf '0x15' ;;
    5) printf '0x1F' ;;
    7) printf '0x7F' ;;
    *)
      echo "Unsupported Maku threshold: $1 (use 0, 1, 3, 5, or 7)" >&2
      exit 1
      ;;
  esac
}

print_next() {
  local message="$1"
  printf '\n[%s] %s\n' "${task}" "${message}"
}

case "${task}" in
  list)
    printf '%s\n' free maku d4 zora d6 d6inside d6cart menu
    ;;
  free)
    launch_instance
    print_next "Instance ready: ${instance}"
    print_next "Next: python3 Scripts/Mesen2/mesen2_client.py --instance ${instance} diagnostics"
    ;;
  maku)
    launch_instance
    crystal_value="$(maku_crystal_value "${maku_crystals}")"
    load_trusted_state_for_task "maku"
    client save-data profile-apply all_items_no_progress >/dev/null
    client setflag gamestate 2 >/dev/null
    client setflag intro true >/dev/null
    client setflag hall false >/dev/null
    client setflag makutree 1 >/dev/null
    client setflag crystals "${crystal_value}" >/dev/null
    client save-data sync-to-sram >/dev/null
    client fly makutree >/dev/null
    client frame 8 >/dev/null
    print_next "Maku Tree session ready on ${instance}"
    print_next "Threshold: ${maku_crystals} crystals (${crystal_value})"
    print_next "Next: talk to the tree and verify message + MapIcon; hall flag should flip on talk"
    ;;
  d4|zora)
    launch_instance
    load_trusted_state_for_task "d4"
    client frame 8 >/dev/null
    print_next "Zora Temple outside seed loaded on ${instance}"
    print_next "Next: walk into the waterfall entrance and validate the transition"
    ;;
  d6)
    launch_instance
    load_trusted_state_for_task "d6"
    client frame 8 >/dev/null
    print_next "D6 overworld entrance seed loaded on ${instance}"
    print_next "Next: walk into the entrance and watch for blackout / stuck submode"
    ;;
  d6inside)
    launch_instance
    load_trusted_state_for_task "d6inside"
    client frame 8 >/dev/null
    print_next "D6 inside entrance seed loaded on ${instance}"
    print_next "Next: test room-to-room transitions from the entrance room"
    ;;
  d6cart)
    launch_instance
    load_trusted_state_for_task "d6cart"
    client frame 8 >/dev/null
    print_next "D6 minecart seed loaded on ${instance}"
    print_next "Next: validate cart shutters, track state, and room transition behavior"
    ;;
  menu)
    launch_instance
    load_trusted_state_for_task "menu"
    client frame 8 >/dev/null
    print_next "Menu/debug slot seed loaded on ${instance}"
    print_next "Next: open the menu and validate UI / item behavior"
    ;;
  *)
    echo "Unknown task: ${task}" >&2
    usage >&2
    exit 1
    ;;
esac
