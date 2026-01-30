#!/bin/bash
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") <version> [asar_binary] [--reload] [--no-symbols] [--mesen-sync] [--skip-tests] [--asar=<path>]" >&2
  echo "Base ROM defaults to Roms/oos<version>_test2.sfc when present, otherwise Roms/oos<version>.sfc (override with OOS_BASE_ROM)." >&2
  exit 1
}

if [[ $# -lt 1 ]]; then
  usage
fi

version="$1"
shift
if ! [[ "$version" =~ ^[0-9]+$ ]]; then
  echo "ERROR: version must be numeric" >&2
  exit 1
fi

reload=0
emit_symbols=1
mesen_sync=0
skip_tests=0
asar_bin="${ASAR_BIN:-asar}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --reload)
      reload=1
      shift
      ;;
    --no-symbols)
      emit_symbols=0
      shift
      ;;
    --mesen-sync)
      mesen_sync=1
      shift
      ;;
    --skip-tests)
      skip_tests=1
      shift
      ;;
    --asar=*)
      asar_bin="${1#--asar=}"
      shift
      ;;
    *)
      asar_bin="$1"
      shift
      ;;
  esac
done

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
rom_dir="$repo_root/Roms"

if [[ "$asar_bin" == "z3asm" ]]; then
  local_z3asm="$repo_root/../z3dk/build/src/z3asm/bin/z3asm"
  if [[ -x "$local_z3asm" ]]; then
    asar_bin="$local_z3asm"
  fi
fi

# ROM naming convention:
#   base_rom    = oos${version}_test2.sfc (dev/edit source) when present
#   patched_rom = oos${version}x.sfc (output after Asar patching)
default_base="$rom_dir/oos${version}.sfc"
test_base="$rom_dir/oos${version}_test2.sfc"
if [[ -z "${OOS_BASE_ROM:-}" ]]; then
  if [[ -f "$test_base" ]]; then
    base_rom="$test_base"
  else
    base_rom="$default_base"
  fi
else
  base_rom="$OOS_BASE_ROM"
fi
patched_rom="$rom_dir/oos${version}x.sfc"
symbols_rel="Roms/oos${version}x.sym"
symbols_path="$rom_dir/oos${version}x.sym"
mlb_rel="Roms/oos${version}x.mlb"
mlb_path="$rom_dir/oos${version}x.mlb"

if [[ -f "$test_base" && "$base_rom" != "$test_base" ]]; then
  echo "WARNING: $test_base exists but base ROM is $base_rom (OOS_BASE_ROM override?)" >&2
fi

if [[ ! -f "$base_rom" ]]; then
  echo "ERROR: Base ROM not found: $base_rom" >&2
  exit 1
fi
echo "Using base ROM: $base_rom"

backup_root="$HOME/Documents/OracleOfSecrets/Roms"
mkdir -p "$backup_root"

if [[ -f "$patched_rom" ]]; then
  timestamp="$(date +"%Y%m%d-%H%M%S")"
  backup_path="$backup_root/oos${version}x_${timestamp}.sfc"
  cp -p "$patched_rom" "$backup_path"
  echo "Archived: $backup_path"
fi

cp -f "$base_rom" "$patched_rom"

if ! command -v "$asar_bin" >/dev/null 2>&1; then
  echo "ERROR: assembler not found: $asar_bin" >&2
  exit 1
fi

if [[ $emit_symbols -eq 1 ]]; then
  # Use z3asm features if available
  if [[ "$asar_bin" == *"z3asm"* ]]; then
    "$asar_bin" --symbols=wla --symbols-path="$symbols_path" --emit=sourcemap.json Oracle_main.asm "$patched_rom"
  else
    "$asar_bin" --symbols=wla --symbols-path="$symbols_path" Oracle_main.asm "$patched_rom"
  fi
else
  "$asar_bin" Oracle_main.asm "$patched_rom"
fi

echo "Built patched ROM: $patched_rom"

# Export symbols for yaze + Mesen2.
if [[ $emit_symbols -eq 1 && -f "$symbols_path" ]]; then
  export_args=("$symbols_rel" "-o" "$mlb_rel" "--rom-name" "oos${version}x" "--filter" "oracle")
  if [[ $mesen_sync -eq 1 ]]; then
    export_args+=("--sync")
  fi
  python3 "$repo_root/scripts/export_symbols.py" "${export_args[@]}"
fi

# Run ZScream overlap check
python3 "$repo_root/scripts/check_zscream_overlap.py"

# Run static analysis if hooks.json exists
hooks_json="$repo_root/hooks.json"
if [[ -f "$patched_rom" ]]; then
  if [[ ! -f "$hooks_json" || "${OOS_GENERATE_HOOKS:-0}" == "1" ]]; then
    echo "[*] Generating hooks.json..."
    python3 "$repo_root/scripts/generate_hooks_json.py" --root "$repo_root" --output "$hooks_json" --rom "$patched_rom" || true
  fi
fi

if [[ -f "$hooks_json" && -f "$patched_rom" ]]; then
  echo "[*] Running static analysis..."
  z3dk_analyzer="$repo_root/../z3dk/scripts/static_analyzer.py"
  oracle_analyzer="$repo_root/../z3dk/scripts/oracle_analyzer.py"

  # Prefer oracle-specific analyzer, fall back to generic
  if [[ -f "$oracle_analyzer" ]]; then
    analyzer_script="$oracle_analyzer"
  elif [[ -f "$z3dk_analyzer" ]]; then
    analyzer_script="$z3dk_analyzer"
  else
    echo "[-] Warning: Static analyzer not found, skipping analysis."
    analyzer_script=""
  fi

  if [[ -n "$analyzer_script" ]]; then
    # Run static analysis - fail build on errors (warnings are OK)
    set +e
    if [[ "$analyzer_script" == *"oracle_analyzer"* ]]; then
      python3 "$analyzer_script" "$patched_rom" --hooks "$hooks_json" --check-hooks --find-mx --find-width-imbalance --check-abi
    else
      python3 "$analyzer_script" "$patched_rom" --hooks "$hooks_json"
    fi
    analysis_exit=$?
    set -e

    if [[ $analysis_exit -ne 0 ]]; then
      echo "[-] Static analysis found errors!"
      if [[ "${OOS_ANALYSIS_FATAL:-1}" == "1" ]]; then
        exit $analysis_exit
      else
        echo "[-] (Non-fatal: set OOS_ANALYSIS_FATAL=1 to block builds)"
      fi
    else
      echo "[+] Static analysis passed."
    fi
  fi
fi

# Run smoke tests (quick validation) unless SKIP_TESTS=1
if [[ "$skip_tests" == "1" || "${SKIP_TESTS:-0}" == "1" ]]; then
  echo "[*] Skipping smoke tests (skip-tests enabled)"
elif [[ -f "$repo_root/scripts/run_regression_tests.sh" ]]; then
  echo "[*] Running smoke tests..."
  set +e
  "$repo_root/scripts/run_regression_tests.sh" smoke --no-moe --fail-fast
  smoke_exit=$?
  set -e

  if [[ $smoke_exit -ne 0 ]]; then
    echo "[-] Smoke tests failed! Build may be broken."
    # Don't fail the build by default - tests require Mesen2 running
    # Uncomment to make test failures fatal:
    # exit $smoke_exit
  else
    echo "[+] Smoke tests passed."
  fi
else
  echo "[*] Skipping smoke tests (runner not found)"
fi

if [[ $reload -eq 1 ]]; then
  echo "[*] Sending reload signal to Mesen2..."
  # Simple reload via socket if mesen2_client.py is available
  if [[ -f "$repo_root/scripts/mesen2_client.py" ]]; then
    python3 "$repo_root/scripts/mesen2_client.py" reset
  else
    echo "[-] Warning: mesen2_client.py not found, skipping reload."
  fi
fi
