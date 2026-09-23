#!/usr/bin/env bash
# Push Oracle of Secrets test ROMs to a USB-connected Anbernic RG353P
# (Android 11, Rockchip RK3566) and optionally launch Snes9x EX Plus.
#
# Patched legacy or hash-named ROMs are emulator targets. The unpatched
# base ROM is refused unless --allow-base is set.
set -euo pipefail

usage() {
  cat <<'EOF'
RG353P handheld deploy helper.

Usage:
  Scripts/Device/oos_rg353p.sh status [handheld helper options]
  Scripts/Device/oos_rg353p.sh capture [handheld helper options]
  Scripts/Device/oos_rg353p.sh collect [--serial SERIAL] [--out DIR] [--json]
  Scripts/Device/oos_rg353p.sh backup [handheld helper options]
  Scripts/Device/oos_rg353p.sh prepare [handheld helper options]
  Scripts/Device/oos_rg353p.sh android-report [--seconds 5] [--serial SERIAL] [--out DIR]
  Scripts/Device/oos_rg353p.sh push [--rom PATH] [--launch|--mesen] [--allow-base]
  Scripts/Device/oos_rg353p.sh launch [--rom-on-device PATH]
  Scripts/Device/oos_rg353p.sh pull-saves [--stem oos168x] [--out DIR]
  Scripts/Device/oos_rg353p.sh install-apk APK
  Scripts/Device/oos_rg353p.sh mesen-build
  Scripts/Device/oos_rg353p.sh mesen-install [--apk PATH]
  Scripts/Device/oos_rg353p.sh mesen-launch [--rom-on-device PATH] [--keep-hud] [--fill-screen]
  Scripts/Device/oos_rg353p.sh mesen-forward [--port 27015]
  Scripts/Device/oos_rg353p.sh mesen-health [--port 27015]
  Scripts/Device/oos_rg353p.sh mesen-stop-debugger [--port 27015]
  Scripts/Device/oos_rg353p.sh mesen-discover [--port 27015]
  Scripts/Device/oos_rg353p.sh mesen-env [--port 27015] [--adb]
  Scripts/Device/oos_rg353p.sh mesen-workshop [--port 27015]
  Scripts/Device/oos_rg353p.sh shell [adb shell args...]

Environment:
  OOS_DEVICE_SERIAL   Select this authorized adb serial
                      (otherwise require exactly one authorized RG353P)
  OOS_DEVICE_SNES_DIR Override SD SNES folder
                      (default /storage/0000-0000/snes)
  OOS_DEVICE_DROP_DIR Override internal drop folder
                      (default /storage/emulated/0/OracleOfSecrets)
  MESEN2_OOS_ROOT     Override sibling Mesen2 checkout for build/install

Status, capture, backup, and prepare options:
  Scripts/Device/oos_rg353p.sh <command> --help

Mesen launch selects the SD ROM first, then the drop folder, then the
existing app copy. Pass --rom-on-device to select a different ROM.
push --mesen backs up saves, copies and launches the exact selected ROM,
then verifies the loaded ROM identity. It cannot be combined with --launch.

Recommended named-build workflow:
  Scripts/Device/oos_rg353p.sh status
  Scripts/Device/oos_rg353p.sh prepare --name minecart-junction --rom Roms/TestBuilds/minecart-junction-2026-09-15/oos168x.sfc
  Scripts/Device/oos_rg353p.sh push --rom <prepared-path> --mesen

Named ROMs use oos-<version>-<YYYYMMDD>-<slug>-<8lowerhex>.sfc.
The hash suffix must match the file's SHA-256 prefix. Legacy oos<ver>x.sfc
remains supported. prepare creates a named copy; it does not rename saves.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEFAULT_SNES_DIR="/storage/0000-0000/snes"
DEFAULT_DROP_DIR="/storage/emulated/0/OracleOfSecrets"
SNES9X_COMPONENT="com.explusalpha.Snes9xPlus/com.imagine.BaseActivity"
SNES9X_PACKAGE="com.explusalpha.Snes9xPlus"
MESEN_PACKAGE="ca.mesen.oos"
MESEN_COMPONENT="ca.mesen.oos/.MesenActivity"
MESEN_TCP_PORT_DEFAULT="27015"
MESEN_APP_FILES="/storage/emulated/0/Android/data/ca.mesen.oos/files"
MESEN2_OOS_ROOT="${MESEN2_OOS_ROOT:-${ROOT_DIR}/../mesen2-oos}"
MESEN_APK_DEFAULT="${MESEN2_OOS_ROOT}/Android/app/build/outputs/apk/debug/app-debug.apk"
HANDHELD_DIR="${ROOT_DIR}/.context/scratchpad/mesen2"
HANDHELD_ENV="${HANDHELD_DIR}/handheld.env"
HANDHELD_JSON="${HANDHELD_DIR}/handheld.json"

die() {
  echo "error: $*" >&2
  exit 1
}

require_adb() {
  command -v adb >/dev/null 2>&1 || die "adb not found. Install with: brew install --cask android-platform-tools"
}

detect_serial() {
  local devices serials count
  devices="$(adb devices -l)" || die "could not list adb devices"
  if [[ -n "${OOS_DEVICE_SERIAL:-}" ]]; then
    if ! awk -v serial="${OOS_DEVICE_SERIAL}" '$1 == serial && $2 == "device" { found=1 } END { exit !found }' <<<"${devices}"; then
      die "adb device ${OOS_DEVICE_SERIAL} is missing, offline, or unauthorized"
    fi
    echo "${OOS_DEVICE_SERIAL}"
    return
  fi

  serials="$(awk '$2 == "device" && /(^|[[:space:]])model:RG353P([[:space:]]|$)/ {print $1}' <<<"${devices}")"
  count="$(awk 'NF {count++} END {print count+0}' <<<"${serials}")"
  [[ "${count}" -gt 0 ]] || die "no authorized RG353P. Connect its charging USB-C port, enable USB debugging, and accept the RSA prompt."
  [[ "${count}" -eq 1 ]] || die "multiple authorized RG353P devices; set OOS_DEVICE_SERIAL to select one"
  echo "${serials}"
}

adb_dev() {
  adb -s "${DEVICE_SERIAL}" "$@"
}

local_sha256() {
  shasum -a 256 "$1" | awk '{print $1}'
}

remote_sha256() {
  local hash
  hash="$(adb_dev shell sha256sum "$1" | awk '{print $1}')" || return 1
  [[ "${hash}" =~ ^[0-9a-fA-F]{64}$ ]] || die "invalid sha256 response for $1"
  echo "${hash}"
}

remote_sha256_as_app() {
  local hash
  hash="$(adb_dev shell run-as "${MESEN_PACKAGE}" sha256sum "$1" | awk '{print $1}')" || return 1
  [[ "${hash}" =~ ^[0-9a-fA-F]{64}$ ]] || die "invalid sha256 response for $1"
  echo "${hash}"
}

resolve_rom() {
  local rom="${1:-}"
  if [[ -z "${rom}" ]]; then
    rom="${ROOT_DIR}/Roms/oos168x.sfc"
  elif [[ "${rom}" != /* ]]; then
    if [[ -f "${ROOT_DIR}/${rom}" ]]; then
      rom="${ROOT_DIR}/${rom}"
    elif [[ -f "${ROOT_DIR}/Roms/${rom}" ]]; then
      rom="${ROOT_DIR}/Roms/${rom}"
    fi
  fi
  [[ -f "${rom}" ]] || die "ROM not found: ${rom}"
  echo "${rom}"
}

assert_test_rom() {
  local rom="$1"
  local allow_base="$2"
  local base
  base="$(basename "${rom}")"
  if [[ "${base}" =~ ^oos[0-9]+x\.sfc$ ]]; then
    return
  fi
  if [[ "${base}" =~ ^oos-[0-9]+-[0-9]{8}-[a-z0-9]+(-[a-z0-9]+)*-([0-9a-f]{8})\.sfc$ ]]; then
    local expected_hash="${BASH_REMATCH[2]}" actual_hash
    actual_hash="$(local_sha256 "${rom}")" || die "could not hash named ROM: ${rom}"
    [[ "${expected_hash}" == "${actual_hash:0:8}" ]] || die "named ROM hash mismatch for ${base}: expected ${expected_hash}, actual ${actual_hash:0:8}"
    return
  fi
  if [[ "${allow_base}" == "1" && "${base}" =~ ^oos[0-9]+\.sfc$ ]]; then
    echo "warning: pushing unpatched/base ROM ${base}" >&2
    return
  fi
  die "refusing ${base}. Use oos<ver>x.sfc or a prepared hash-named ROM; --allow-base permits only oos<ver>.sfc"
}

media_scan() {
  local path="$1"
  adb_dev shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://${path}" >/dev/null
}

content_uri_for() {
  local path="$1"
  local row id
  media_scan "${path}"
  row="$(adb_dev shell content query --uri content://media/external/file --projection _id --where "_data=\\'${path}\\'" 2>/dev/null | tr -d '\r' | head -1)"
  if [[ -z "${row}" || "${row}" != *_id=* ]]; then
    sleep 0.4
    media_scan "${path}"
    row="$(adb_dev shell content query --uri content://media/external/file --projection _id --where "_data=\\'${path}\\'" 2>/dev/null | tr -d '\r' | head -1)"
  fi
  id="${row##*_id=}"
  id="${id%%,*}"
  [[ "${id}" =~ ^[0-9]+$ ]] || return 1
  echo "content://media/external/file/${id}"
}

push_one() {
  local src="$1"
  local dest="$2"
  local local_hash remote_hash dest_dir
  dest_dir="$(dirname "${dest}")"
  adb_dev shell mkdir -p "${dest_dir}"
  echo "push: ${src} -> ${DEVICE_SERIAL}:${dest}"
  adb_dev push "${src}" "${dest}" >/dev/null
  local_hash="$(local_sha256 "${src}")"
  remote_hash="$(remote_sha256 "${dest}")"
  [[ "${local_hash}" == "${remote_hash}" ]] || die "sha256 mismatch for ${dest} (local ${local_hash} remote ${remote_hash})"
  media_scan "${dest}"
  echo "ok:   ${dest}  sha256=${local_hash}"
}

cmd_push() {
  local rom="" launch="0" mesen="0" allow_base="0"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --rom) rom="$2"; shift 2 ;;
      --launch) launch="1"; shift ;;
      --mesen) mesen="1"; shift ;;
      --allow-base) allow_base="1"; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown push arg: $1" ;;
    esac
  done

  [[ "${launch}" != "1" || "${mesen}" != "1" ]] || die "--launch and --mesen cannot be combined"
  rom="$(resolve_rom "${rom}")"
  assert_test_rom "${rom}" "${allow_base}"
  local name source_hash
  name="$(basename "${rom}")"
  source_hash="$(local_sha256 "${rom}")" || die "could not hash ROM: ${rom}"

  if [[ "${mesen}" == "1" ]]; then
    OOS_DEVICE_SERIAL="${DEVICE_SERIAL}" python3 "${SCRIPT_DIR}/oos_handheld.py" backup || die "save backup failed; ROM deployment aborted"
  fi

  push_one "${rom}" "${SNES_DIR}/${name}"
  push_one "${rom}" "${DROP_DIR}/${name}"

  if [[ "${mesen}" == "1" ]]; then
    cmd_mesen_launch --rom-on-device "${SNES_DIR}/${name}"
    OOS_DEVICE_SERIAL="${DEVICE_SERIAL}" python3 "${SCRIPT_DIR}/oos_handheld.py" status --expect-sha256 "${source_hash}"
  elif [[ "${launch}" == "1" ]]; then
    cmd_launch --rom-on-device "${SNES_DIR}/${name}"
  fi
}

cmd_launch() {
  local remote="${SNES_DIR}/oos168x.sfc"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --rom-on-device) remote="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown launch arg: $1" ;;
    esac
  done

  adb_dev shell "test -f '${remote}'" || die "device ROM missing: ${remote}"
  local uri
  uri="$(content_uri_for "${remote}" || true)"
  if [[ -z "${uri}" ]]; then
    echo "warning: MediaStore has no id for ${remote}; falling back to file://" >&2
    uri="file://${remote}"
  fi
  echo "launch: ${SNES9X_PACKAGE} ${uri}"
  adb_dev shell am force-stop "${SNES9X_PACKAGE}" >/dev/null
  adb_dev shell am start \
    -a android.intent.action.VIEW \
    -d "${uri}" \
    -t application/octet-stream \
    --grant-read-uri-permission \
    -n "${SNES9X_COMPONENT}"
}

cmd_pull_saves() {
  local stem="oos168x" out="${ROOT_DIR}/Roms/device-saves"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --stem) stem="$2"; shift 2 ;;
      --out) out="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown pull-saves arg: $1" ;;
    esac
  done
  mkdir -p "${out}"
  local pulled=0
  local ext
  for ext in srm frz 00.frz 0A.frz cht config sav rtc; do
    local src="${SNES_DIR}/${stem}.${ext}"
    if adb_dev shell "test -f '${src}'"; then
      adb_dev pull "${src}" "${out}/" >/dev/null
      echo "pulled ${src}"
      pulled=$((pulled + 1))
    fi
  done
  [[ "${pulled}" -gt 0 ]] || die "no save/sidecar files for ${stem} in ${SNES_DIR}"
  echo "saved to ${out}"
}

cmd_install_apk() {
  [[ $# -ge 1 ]] || die "install-apk requires an APK path"
  local apk="$1"
  [[ -f "${apk}" ]] || die "APK not found: ${apk}"
  echo "install: ${apk}"
  adb_dev install -r "${apk}"
}

cmd_mesen_build() {
  local build_sh="${MESEN2_OOS_ROOT}/Android/build.sh"
  [[ -x "${build_sh}" || -f "${build_sh}" ]] || die "missing ${build_sh}"
  bash "${build_sh}"
}

cmd_mesen_install() {
  local apk="${MESEN_APK_DEFAULT}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --apk) apk="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown mesen-install arg: $1" ;;
    esac
  done
  [[ -f "${apk}" ]] || die "APK not found: ${apk}. Run mesen-build first."
  echo "install: ${apk}"
  adb_dev install -r "${apk}"
}

cmd_mesen_launch() {
  local remote=""
  local keep_hud=0
  local fill_screen=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --rom-on-device) remote="$2"; shift 2 ;;
      --keep-hud) keep_hud=1; shift ;;
      --fill-screen) fill_screen=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown mesen-launch arg: $1" ;;
    esac
  done
  adb_dev shell pm path "${MESEN_PACKAGE}" >/dev/null 2>&1 || die "Mesen2-OOS is not installed. Run mesen-install."
  adb_dev shell mkdir -p "${MESEN_APP_FILES}"
  local staged="${MESEN_APP_FILES}/oos168x.sfc"
  if [[ -z "${remote}" ]]; then
    if adb_dev shell "test -f '${SNES_DIR}/oos168x.sfc'"; then
      remote="${SNES_DIR}/oos168x.sfc"
    elif adb_dev shell "test -f '${DROP_DIR}/oos168x.sfc'"; then
      remote="${DROP_DIR}/oos168x.sfc"
    else
      remote="${staged}"
    fi
  fi
  adb_dev shell "test -f '${remote}'" || die "device ROM missing: ${remote}"
  local source_hash staged_hash internal_hash
  source_hash="$(remote_sha256 "${remote}")" || die "could not hash source ROM: ${remote}"
  staged="${MESEN_APP_FILES}/$(basename "${remote}")"
  if [[ "${remote}" != "${staged}" ]]; then
    adb_dev shell "cp '${remote}' '${staged}' && chmod 644 '${staged}'" >/dev/null || die "failed to stage ROM at ${staged}"
  fi
  staged_hash="$(remote_sha256 "${staged}")" || die "could not hash staged ROM: ${staged}"
  [[ "${source_hash}" == "${staged_hash}" ]] || die "sha256 mismatch for staged ROM: ${staged}"
  local internal="/data/data/${MESEN_PACKAGE}/files/$(basename "${staged}")"
  adb_dev shell run-as "${MESEN_PACKAGE}" mkdir -p "/data/data/${MESEN_PACKAGE}/files" >/dev/null \
    || die "failed to prepare app-private ROM storage; launch aborted"
  adb_dev shell run-as "${MESEN_PACKAGE}" cp "${staged}" "${internal}" >/dev/null \
    || die "failed to copy internal ROM: ${internal}; launch aborted"
  adb_dev shell run-as "${MESEN_PACKAGE}" chmod 600 "${internal}" >/dev/null \
    || die "failed to protect internal ROM: ${internal}; launch aborted"
  internal_hash="$(remote_sha256_as_app "${internal}")" || die "could not hash internal ROM: ${internal}"
  [[ "${source_hash}" == "${internal_hash}" ]] || die "sha256 mismatch for internal ROM: ${internal}"
  echo "verified: source=${remote} staged=${staged} internal=${internal} sha256=${source_hash}"
  adb_dev shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1 || true
  adb_dev shell wm dismiss-keyguard >/dev/null 2>&1 || true
  adb_dev shell cmd statusbar collapse >/dev/null 2>&1 || true
  adb_dev shell am broadcast -a android.intent.action.CLOSE_SYSTEM_DIALOGS >/dev/null 2>&1 || true
  echo "launch: ${MESEN_PACKAGE} rom=${staged}"
  adb_dev shell am force-stop "${SNES9X_PACKAGE}" >/dev/null 2>&1 || true
  adb_dev shell am force-stop "${MESEN_PACKAGE}" >/dev/null
  local extras=( --es rom "${staged}" )
  if [[ "${keep_hud}" -eq 1 ]]; then
    extras+=( --ez keep_hud true )
  fi
  if [[ "${fill_screen}" -eq 1 ]]; then
    extras+=( --ez fill_screen true )
  fi
  adb_dev shell am start \
    -n "${MESEN_COMPONENT}" \
    -a android.intent.action.MAIN \
    -c android.intent.category.LAUNCHER \
    --activity-brought-to-front \
    "${extras[@]}"
  sleep 1
  adb_dev shell wm dismiss-keyguard >/dev/null 2>&1 || true
  adb_dev shell cmd statusbar collapse >/dev/null 2>&1 || true
}

cmd_mesen_forward() {
  local port="${MESEN_TCP_PORT_DEFAULT}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --port) port="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown mesen-forward arg: $1" ;;
    esac
  done
  echo "forward: tcp:${port} -> device tcp:${port}"
  adb_dev forward "tcp:${port}" "tcp:${port}"
}

cmd_mesen_health() {
  local port="${MESEN_TCP_PORT_DEFAULT}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --port) port="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown mesen-health arg: $1" ;;
    esac
  done
  cmd_mesen_forward --port "${port}"
  echo "health: MESEN2_SOCKET_PATH=tcp://127.0.0.1:${port}"
  MESEN2_SOCKET_PATH="tcp://127.0.0.1:${port}" python3 "${ROOT_DIR}/Scripts/Mesen2/mesen2_client.py" health
}

cmd_mesen_stop_debugger() {
  local port="${MESEN_TCP_PORT_DEFAULT}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --port) port="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown mesen-stop-debugger arg: $1" ;;
    esac
  done
  cmd_mesen_forward --port "${port}"
  MESEN2_SOCKET_PATH="tcp://127.0.0.1:${port}" \
    python3 "${ROOT_DIR}/Scripts/Mesen2/mesen2_client.py" stop-debugger
}

cmd_mesen_pull_workshop() {
  local tmp dest="${1:-}"
  tmp="$(mktemp)"
  if adb_dev shell run-as "${MESEN_PACKAGE}" cat files/workshop.json >"${tmp}" 2>/dev/null \
      || adb_dev pull "${MESEN_APP_FILES}/workshop.json" "${tmp}" >/dev/null 2>&1 \
      || adb_dev pull "${DROP_DIR}/workshop.json" "${tmp}" >/dev/null 2>&1; then
    if [[ -n "${dest}" ]]; then
      cp "${tmp}" "${dest}"
    else
      cat "${tmp}"
    fi
    rm -f "${tmp}"
    return 0
  fi
  rm -f "${tmp}"
  return 1
}

cmd_mesen_discover() {
  local port="${MESEN_TCP_PORT_DEFAULT}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --port) port="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown mesen-discover arg: $1" ;;
    esac
  done
  echo "serial: ${DEVICE_SERIAL}"
  echo "package: ${MESEN_PACKAGE}"
  local pid
  pid="$(adb_dev shell pidof "${MESEN_PACKAGE}" 2>/dev/null | tr -d '\r' || true)"
  echo "pid: ${pid:-none}"
  echo "adb: tcp://127.0.0.1:${port}"
  echo "workshop:"
  if ! cmd_mesen_pull_workshop; then
    echo "  (not written yet — open Workshop once on the handheld)"
  fi
  echo
  echo "attach:"
  echo "  Scripts/Device/oos_rg353p.sh mesen-env"
  echo "  source ${HANDHELD_ENV}"
  echo "  python3 Scripts/Mesen2/mesen2_client.py health"
  echo "  python3 Scripts/Mesen2/mesen2_client.py mem-read 0x7E0010 --len 2"
  echo "  MESEN2_SOCKET_PATH=tcp://127.0.0.1:${port} z3ed mesen-gamestate"
}

cmd_mesen_env() {
  local port="${MESEN_TCP_PORT_DEFAULT}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --port) port="$2"; shift 2 ;;
      --adb) shift ;;
      --lan) die "LAN attach is disabled; Workshop is loopback-only, so use --adb" ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown mesen-env arg: $1" ;;
    esac
  done
  mkdir -p "${HANDHELD_DIR}"
  cmd_mesen_pull_workshop "${HANDHELD_DIR}/workshop.json" || true
  local socket="tcp://127.0.0.1:${port}"
  cmd_mesen_forward --port "${port}"
  cat > "${HANDHELD_ENV}" <<EOF
export MESEN2_HANDHELD=1
export MESEN2_SOCKET_PATH=${socket}
export MESEN2_TCP_HOST=127.0.0.1
export MESEN2_TCP_PORT=${port}
export OOS_DEVICE_SERIAL=${DEVICE_SERIAL}
EOF
  python3 - <<PY
import json
from pathlib import Path
path = Path("${HANDHELD_JSON}")
data = {
  "socket": "${socket}",
  "via": "adb",
  "serial": "${DEVICE_SERIAL}",
  "package": "${MESEN_PACKAGE}",
  "workshop": str(Path("${HANDHELD_DIR}") / "workshop.json"),
}
path.write_text(json.dumps(data, indent=2) + "\n")
PY
  echo "wrote ${HANDHELD_ENV}"
  echo "wrote ${HANDHELD_JSON}"
  echo "source ${HANDHELD_ENV}"
}

cmd_mesen_workshop() {
  local port="${MESEN_TCP_PORT_DEFAULT}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --port) port="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown mesen-workshop arg: $1" ;;
    esac
  done
  OOS_DEVICE_SERIAL="${DEVICE_SERIAL}" python3 "${SCRIPT_DIR}/oos_handheld.py" capture --port "${port}"
}

main() {
  [[ $# -gt 0 ]] || { usage; exit 1; }
  local cmd="$1"
  shift
  case "${cmd}" in
    -h|--help) usage; exit 0 ;;
    android-report) exec python3 "${SCRIPT_DIR}/oos_android_report.py" "$@" ;;
    status|capture|backup|prepare) exec python3 "${SCRIPT_DIR}/oos_handheld.py" "${cmd}" "$@" ;;
    collect) exec python3 "${SCRIPT_DIR}/oos_workshop_collect.py" "$@" ;;
  esac

  require_adb
  DEVICE_SERIAL="$(detect_serial)"
  SNES_DIR="${OOS_DEVICE_SNES_DIR:-${DEFAULT_SNES_DIR}}"
  DROP_DIR="${OOS_DEVICE_DROP_DIR:-${DEFAULT_DROP_DIR}}"

  case "${cmd}" in
    push) cmd_push "$@" ;;
    launch) cmd_launch "$@" ;;
    pull-saves) cmd_pull_saves "$@" ;;
    install-apk) cmd_install_apk "$@" ;;
    mesen-build) cmd_mesen_build "$@" ;;
    mesen-install) cmd_mesen_install "$@" ;;
    mesen-launch) cmd_mesen_launch "$@" ;;
    mesen-forward) cmd_mesen_forward "$@" ;;
    mesen-health) cmd_mesen_health "$@" ;;
    mesen-stop-debugger) cmd_mesen_stop_debugger "$@" ;;
    mesen-discover) cmd_mesen_discover "$@" ;;
    mesen-env) cmd_mesen_env "$@" ;;
    mesen-workshop) cmd_mesen_workshop "$@" ;;
    shell) adb_dev shell "$@" ;;
    *) die "unknown command: ${cmd}" ;;
  esac
}

main "$@"
