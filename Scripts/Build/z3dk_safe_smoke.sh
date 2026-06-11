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

default_base="${ROOT_DIR}/Roms/oos${version}.sfc"
legacy_base="${ROOT_DIR}/Roms/oos${version}_test2.sfc"
if [[ -z "${OOS_BASE_ROM:-}" ]]; then
  if [[ -f "$legacy_base" ]]; then
    base_rom="$legacy_base"
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

echo "[z3dk-smoke] Repo root: ${ROOT_DIR}"
echo "[z3dk-smoke] Base ROM copy: ${temp_base}"
echo "[z3dk-smoke] Patched ROM target: ${temp_patched}"
echo "[z3dk-smoke] z3asm: $(command -v "$z3asm_bin")"

build_cmd=("$z3asm_bin")
if [[ "$emit_symbols" == "1" ]]; then
  build_cmd+=(--symbols=wla "--symbols-path=${temp_symbols}")
fi
build_cmd+=(Oracle_main.asm "$temp_patched")

(
  cd "$ROOT_DIR"
  "${build_cmd[@]}"
) >"$temp_stdout" 2>"$temp_stderr"

status=0
echo "[z3dk-smoke] Build succeeded."
echo "[z3dk-smoke] Patched ROM: ${temp_patched}"
if [[ "$emit_symbols" == "1" && -f "$temp_symbols" ]]; then
  echo "[z3dk-smoke] Symbols: ${temp_symbols}"
fi
echo "[z3dk-smoke] Stdout log: ${temp_stdout}"
echo "[z3dk-smoke] Stderr log: ${temp_stderr}"
