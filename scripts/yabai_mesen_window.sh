#!/usr/bin/env bash
# Toggle or control the Mesen2 window layer using yabai.

set -euo pipefail

APP_NAME="${APP_NAME:-Mesen,Mesen2}"
ACTION="${1:-toggle}"
SCRATCH_SPACE="${SCRATCH_SPACE:-}"
STATE_FILE="${STATE_FILE:-${HOME}/Documents/Mesen2/bridge/mesen_space.txt}"
TITLE_REGEX="${TITLE_REGEX:-}"

if ! command -v yabai >/dev/null 2>&1; then
  echo "yabai not found in PATH." >&2
  exit 1
fi

find_window_ids() {
  yabai -m query --windows | python3 - <<'PY'
import json, os, re, sys
apps_raw = os.environ.get("APP_NAME", "Mesen,Mesen2")
apps = [a.strip() for a in apps_raw.split(",") if a.strip()]
title_re = os.environ.get("TITLE_REGEX","").strip()
title_re = re.compile(title_re) if title_re else None
try:
    windows = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(1)
for win in windows:
    if win.get("app") not in apps:
        continue
    title = win.get("title") or ""
    if title_re and not title_re.search(title):
        continue
    print(win.get("id", ""))
PY
}

find_space_index() {
  local wid="$1"
  yabai -m query --windows --window "$wid" | python3 - <<'PY'
import json, sys
try:
    d = json.load(sys.stdin)
except json.JSONDecodeError:
    print("")
    sys.exit(0)
print(d.get("space", ""))
PY
}

get_layer() {
  local wid="$1"
  yabai -m query --windows --window "$wid" | python3 - <<'PY'
import json, sys
try:
    d = json.load(sys.stdin)
except json.JSONDecodeError:
    print("")
    sys.exit(0)
print(d.get("layer", ""))
PY
}

mapfile -t window_ids < <(find_window_ids || true)
if [[ "${#window_ids[@]}" -eq 0 ]]; then
  echo "No ${APP_NAME} window found." >&2
  exit 1
fi

primary_id="${window_ids[0]}"
layer="$(get_layer "${primary_id}")"
space_idx="$(find_space_index "${primary_id}")"

case "${ACTION}" in
  show)
    for wid in "${window_ids[@]}"; do
      yabai -m window "${wid}" --layer normal >/dev/null || true
    done
    yabai -m window "${primary_id}" --focus >/dev/null || true
    ;;
  hide|background|below)
    for wid in "${window_ids[@]}"; do
      yabai -m window "${wid}" --layer below >/dev/null || true
    done
    ;;
  focus)
    yabai -m window "${primary_id}" --focus >/dev/null || true
    ;;
  minimize)
    for wid in "${window_ids[@]}"; do
      yabai -m window "${wid}" --minimize >/dev/null || true
    done
    ;;
  restore|deminimize)
    for wid in "${window_ids[@]}"; do
      yabai -m window "${wid}" --deminimize >/dev/null || true
    done
    ;;
  space)
    target="${2:-${SCRATCH_SPACE}}"
    if [[ -z "${target}" ]]; then
      echo "Missing target space. Provide as arg or SCRATCH_SPACE env var." >&2
      exit 1
    fi
    for wid in "${window_ids[@]}"; do
      yabai -m window "${wid}" --space "${target}" >/dev/null || true
    done
    ;;
  stash)
    target="${2:-${SCRATCH_SPACE}}"
    if [[ -z "${target}" ]]; then
      echo "Missing target space. Provide as arg or SCRATCH_SPACE env var." >&2
      exit 1
    fi
    if [[ -n "${space_idx}" ]]; then
      mkdir -p "$(dirname "${STATE_FILE}")"
      echo "${space_idx}" > "${STATE_FILE}"
    fi
    for wid in "${window_ids[@]}"; do
      yabai -m window "${wid}" --space "${target}" >/dev/null || true
    done
    ;;
  unstash)
    if [[ ! -f "${STATE_FILE}" ]]; then
      echo "No saved space state at ${STATE_FILE}" >&2
      exit 1
    fi
    target="$(cat "${STATE_FILE}")"
    if [[ -z "${target}" ]]; then
      echo "Saved space index is empty." >&2
      exit 1
    fi
    for wid in "${window_ids[@]}"; do
      yabai -m window "${wid}" --space "${target}" >/dev/null || true
    done
    ;;
  toggle-space)
    target="${2:-${SCRATCH_SPACE}}"
    if [[ -z "${target}" ]]; then
      echo "Missing target space. Provide as arg or SCRATCH_SPACE env var." >&2
      exit 1
    fi
    if [[ "${space_idx}" == "${target}" ]]; then
      if [[ -f "${STATE_FILE}" ]]; then
        prev="$(cat "${STATE_FILE}")"
        if [[ -n "${prev}" ]]; then
          for wid in "${window_ids[@]}"; do
            yabai -m window "${wid}" --space "${prev}" >/dev/null || true
          done
        fi
      fi
    else
      if [[ -n "${space_idx}" ]]; then
        mkdir -p "$(dirname "${STATE_FILE}")"
        echo "${space_idx}" > "${STATE_FILE}"
      fi
      for wid in "${window_ids[@]}"; do
        yabai -m window "${wid}" --space "${target}" >/dev/null || true
      done
    fi
    ;;
  toggle)
    any_normal=0
    for wid in "${window_ids[@]}"; do
      if [[ "$(get_layer "${wid}")" != "below" ]]; then
        any_normal=1
        break
      fi
    done
    if [[ "${any_normal}" -eq 1 ]]; then
      for wid in "${window_ids[@]}"; do
        yabai -m window "${wid}" --layer below >/dev/null || true
      done
    else
      for wid in "${window_ids[@]}"; do
        yabai -m window "${wid}" --layer normal >/dev/null || true
      done
      yabai -m window "${primary_id}" --focus >/dev/null || true
    fi
    ;;
  *)
    cat <<'EOF' >&2
Usage: yabai_mesen_window.sh [show|hide|toggle|focus|background|minimize|restore|space|stash|unstash|toggle-space]
Defaults to toggle. Set APP_NAME to override (default: Mesen).
Optional TITLE_REGEX to filter windows by title.
Space actions use SCRATCH_SPACE env var or an explicit space index.
EOF
    exit 1
    ;;
esac
