#!/usr/bin/env bash
# Manage yabai rules for Mesen/Mesen2 to avoid unwanted tiling.

set -euo pipefail

ACTION="${1:-status}"
MODE="${2:-float}"
SPACE="${3:-}"

if ! command -v yabai >/dev/null 2>&1; then
  echo "yabai not found in PATH." >&2
  exit 1
fi

list_rules() {
  yabai -m rule --list
}

remove_mesen_rules() {
  local raw
  raw="$(list_rules || true)"
  RAW="${raw}" python3 - <<'PY'
import json, os, subprocess, sys
raw = os.environ.get("RAW","").strip()
if not raw:
    sys.exit(0)
try:
    rules = json.loads(raw)
except json.JSONDecodeError:
    sys.exit(0)
indices = [r.get("index") for r in rules if ("Mesen" in (r.get("app") or "") or "Mesen" in (r.get("label") or ""))]
indices = [i for i in indices if i is not None]
indices.sort(reverse=True)
for idx in indices:
    subprocess.run(["yabai","-m","rule","--remove",str(idx)], check=False)
PY
}

apply_rule() {
  local mode="$1"
  local space="$2"
  local base_rule=( "app=^(Mesen|Mesen2|Mesen2 OOS)$" "label=mesen-managed" )
  case "${mode}" in
    bsp)
      yabai -m rule --add "${base_rule[@]}" "manage=on" >/dev/null
      ;;
    float)
      yabai -m rule --add "${base_rule[@]}" "manage=off" "grid=6:6:4:0:2:3" >/dev/null
      ;;
    background|below|bg)
      yabai -m rule --add "${base_rule[@]}" "manage=off" "grid=6:6:4:0:2:3" >/dev/null
      ;;
    space)
      if [[ -z "${space}" ]]; then
        echo "Missing space index for mode 'space'." >&2
        exit 1
      fi
      yabai -m rule --add "${base_rule[@]}" "manage=off" "space=${space}" >/dev/null
      ;;
    off)
      ;;
    *)
      echo "Unknown mode: ${mode}" >&2
      exit 1
      ;;
  esac
}

apply_aux_rules() {
  # Float tool windows (Script/Debugger/etc.) to avoid bsp tiling chaos
  local aux_rule=( "app=^(Mesen|Mesen2|Mesen2 OOS)$" "label=mesen-aux" "manage=off" )
  local titles="(Script|Lua|Debugger|Trace|Profiler|Disassembler|Memory|Palette|Tile|Assembler|Log|Breakpoints|Cheats|Input|Settings|PPU|APU|Event|Watch|Viewer|Mixer)"
  yabai -m rule --add "${aux_rule[@]}" "title=${titles}" >/dev/null || true
}

apply_existing() {
  local mode="$1"
  local titles="(Script|Lua|Debugger|Trace|Profiler|Disassembler|Memory|Palette|Tile|Assembler|Log|Breakpoints|Cheats|Input|Settings|PPU|APU|Event|Watch|Viewer|Mixer)"
  MODE="${mode}" TITLES="${titles}" yabai -m query --windows | python3 - <<'PY'
import json, os, re, subprocess, sys
mode = os.environ.get("MODE", "")
titles = os.environ.get("TITLES", "")
try:
    windows = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)
title_re = re.compile(titles) if titles else None
for win in windows:
    app = win.get("app") or ""
    if app not in ("Mesen", "Mesen2", "Mesen2 OOS"):
        continue
    wid = win.get("id")
    if not wid:
        continue
    is_floating = bool(win.get("is-floating", False))
    title = win.get("title") or ""
    is_aux = bool(title_re.search(title)) if title_re else False
    if mode in ("float", "background", "bg", "space"):
        if not is_floating:
            subprocess.run(["yabai", "-m", "window", str(wid), "--toggle", "float"], check=False)
    elif mode == "bsp":
        if is_aux and not is_floating:
            subprocess.run(["yabai", "-m", "window", str(wid), "--toggle", "float"], check=False)
PY
}

case "${ACTION}" in
  status)
    raw="$(list_rules || true)"
    RAW="${raw}" python3 - <<'PY'
import json, os, sys
raw = os.environ.get("RAW","").strip()
if not raw:
    sys.exit(0)
try:
    rules = json.loads(raw)
except json.JSONDecodeError:
    sys.exit(0)
for r in rules:
    app = r.get("app") or ""
    label = r.get("label") or ""
    if "Mesen" in app or "Mesen" in label:
        print(r)
PY
    ;;
  reset)
    remove_mesen_rules
    ;;
  apply)
    remove_mesen_rules
    if [[ "${MODE}" != "off" ]]; then
      apply_rule "${MODE}" "${SPACE}"
      apply_aux_rules
      apply_existing "${MODE}"
    fi
    ;;
  refresh)
    apply_existing "${MODE}"
    ;;
  *)
    cat <<'EOF' >&2
Usage: yabai_mesen_rules.sh [status|reset|apply|refresh] [mode] [space]
Modes: bsp | float | background | space | off
EOF
    exit 1
    ;;
esac
