#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Safe Oracle z3dk smoke build.

Copies the selected base ROM into a temp workspace, assembles the patched ROM
there, and writes logs/symbols beside the temp copy. The checked-in patched ROM
under Roms/ is never touched.

Usage:
  Scripts/Build/z3dk_safe_smoke.sh [version] [options]

Options:
  --version N        ROM version (default: 168)
  --z3asm PATH       z3asm binary to use (default: z3asm from PATH)
  --temp-root DIR    Parent directory for temp workspace (default: TMPDIR or /tmp)
  --timeout SECONDS  Stop z3asm after this many seconds (default: 600)
  --keep-temp        Keep temp workspace after a successful build
  --no-symbols       Skip WLA symbol output
  -h, --help         Show this message

Examples:
  Scripts/Build/z3dk_safe_smoke.sh
  Scripts/Build/z3dk_safe_smoke.sh 168 --keep-temp
  Scripts/Build/z3dk_safe_smoke.sh --z3asm /Users/scawful/src/tools/z3dk-install/bin/z3asm
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

version=""
z3asm_bin="${OOS_Z3ASM_BIN:-z3asm}"
temp_root="${TMPDIR:-/tmp}"
keep_temp=0
emit_symbols=1
timeout_seconds="${OOS_Z3ASM_TIMEOUT_SECONDS:-600}"

if [[ $# -gt 0 && "${1}" != "-"* ]]; then
  version="$1"
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      version="${2:-}"
      shift 2
      ;;
    --z3asm)
      z3asm_bin="${2:-}"
      shift 2
      ;;
    --temp-root)
      temp_root="${2:-}"
      shift 2
      ;;
    --timeout)
      timeout_seconds="${2:-}"
      shift 2
      ;;
    --keep-temp)
      keep_temp=1
      shift
      ;;
    --no-symbols)
      emit_symbols=0
      shift
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

version="${version:-168}"

if ! [[ "$version" =~ ^[0-9]+$ ]]; then
  echo "ERROR: version must be numeric (got: $version)" >&2
  exit 1
fi

if ! [[ "$timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: timeout must be a positive integer (got: $timeout_seconds)" >&2
  exit 1
fi

default_base="${ROOT_DIR}/Roms/oos${version}.sfc"
legacy_base="${ROOT_DIR}/Roms/oos${version}_test2.sfc"
if [[ -z "${OOS_BASE_ROM:-}" ]]; then
  if [[ -f "$default_base" ]]; then
    base_rom="$default_base"
  elif [[ -f "$legacy_base" ]]; then
    base_rom="$legacy_base"
    echo "NOTE: Using legacy base ROM name $(basename "$legacy_base"). Rename to $(basename "$default_base") to adopt standard naming." >&2
  else
    base_rom="$default_base"
  fi
else
  base_rom="$OOS_BASE_ROM"
fi

if [[ ! -f "$base_rom" ]]; then
  echo "ERROR: Base ROM not found: $base_rom" >&2
  exit 1
fi

if ! command -v "$z3asm_bin" >/dev/null 2>&1; then
  echo "ERROR: z3asm not found: $z3asm_bin" >&2
  exit 1
fi

mkdir -p "$temp_root"
temp_dir="$(mktemp -d "${temp_root%/}/oos-z3dk-smoke.${version}.XXXXXX")"
temp_base="${temp_dir}/oos${version}.sfc"
temp_patched="${temp_dir}/oos${version}x.sfc"
temp_symbols="${temp_dir}/oos${version}x.sym"
temp_stdout="${temp_dir}/z3asm.stdout.log"
temp_stderr="${temp_dir}/z3asm.stderr.log"
status=1

cleanup() {
  if [[ "$keep_temp" == "1" || "$status" != "0" ]]; then
    echo "[z3dk-smoke] Temp workspace retained: ${temp_dir}"
  else
    rm -rf "$temp_dir"
  fi
}
trap cleanup EXIT

cp -f "$base_rom" "$temp_base"
cp -f "$temp_base" "$temp_patched"

echo "[z3dk-smoke] Repo root: ${ROOT_DIR}"
echo "[z3dk-smoke] Base ROM source: ${base_rom}"
echo "[z3dk-smoke] Base ROM copy: ${temp_base}"
echo "[z3dk-smoke] Patched ROM target: ${temp_patched}"
echo "[z3dk-smoke] z3asm: $(command -v "$z3asm_bin")"
echo "[z3dk-smoke] Timeout: ${timeout_seconds}s"

build_cmd=("$z3asm_bin")
if [[ "$emit_symbols" == "1" ]]; then
  build_cmd+=(--symbols=wla "--symbols-path=${temp_symbols}")
fi
build_cmd+=(Oracle_main.asm "$temp_patched")

timeout_marker="${temp_dir}/z3asm.timeout"
set +e
python3 - "$ROOT_DIR" "$timeout_seconds" "$temp_stdout" "$temp_stderr" "$timeout_marker" "${build_cmd[@]}" <<'PY'
import os
import signal
import subprocess
import sys
from pathlib import Path

root, timeout_raw, stdout_path, stderr_path, marker_path, *command = sys.argv[1:]
with open(stdout_path, "wb") as stdout, open(stderr_path, "wb") as stderr:
    process = subprocess.Popen(
        command,
        cwd=root,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
    )
    try:
        build_status = process.wait(timeout=int(timeout_raw))
    except subprocess.TimeoutExpired:
        Path(marker_path).write_text(
            f"z3asm exceeded {timeout_raw} seconds\n", encoding="utf-8"
        )
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        raise SystemExit(124)

raise SystemExit(build_status if build_status >= 0 else 128 - build_status)
PY
build_status=$?
set -e

if [[ -f "$timeout_marker" ]]; then
  echo "ERROR: z3asm timed out after ${timeout_seconds}s" >&2
  exit 1
fi

if [[ "$build_status" != "0" ]]; then
  echo "ERROR: z3asm failed with exit code ${build_status}" >&2
  [[ ! -s "$temp_stderr" ]] || tail -n 40 "$temp_stderr" >&2
  exit "$build_status"
fi

if [[ ! -f "$temp_patched" ]]; then
  echo "ERROR: z3asm did not produce the patched ROM: ${temp_patched}" >&2
  exit 1
fi

base_size="$(wc -c <"$temp_base" | tr -d '[:space:]')"
patched_size="$(wc -c <"$temp_patched" | tr -d '[:space:]')"
max_lorom_size=$((4 * 1024 * 1024))
if (( patched_size < base_size )); then
  echo "ERROR: Patched ROM was truncated (${base_size} -> ${patched_size} bytes)" >&2
  exit 1
fi
if (( patched_size > max_lorom_size )); then
  echo "ERROR: Patched ROM exceeds the 4 MiB LoROM limit (${patched_size} bytes)" >&2
  exit 1
fi

if cmp -s "$temp_base" "$temp_patched"; then
  echo "ERROR: z3asm completed without changing the seeded ROM" >&2
  exit 1
fi

if ! cmp -s "$base_rom" "$temp_base"; then
  echo "ERROR: Base ROM source changed during the smoke build: ${base_rom}" >&2
  exit 1
fi

status=0
echo "[z3dk-smoke] Build succeeded."
echo "[z3dk-smoke] Patched ROM: ${temp_patched}"
if [[ "$emit_symbols" == "1" && -f "$temp_symbols" ]]; then
  echo "[z3dk-smoke] Symbols: ${temp_symbols}"
fi
echo "[z3dk-smoke] Stdout log: ${temp_stdout}"
echo "[z3dk-smoke] Stderr log: ${temp_stderr}"
