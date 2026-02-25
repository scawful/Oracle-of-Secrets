#!/bin/bash
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") <version> [asar_binary] [--reload] [--no-symbols] [--mesen-sync] [--skip-tests] [--asar=<path>] [--enable <csv>] [--disable <csv>] [--profile <defaults|all-on|all-off>] [--persist-flags]" >&2
  echo "Base ROM defaults to Roms/oos<version>_test2.sfc when present, otherwise Roms/oos<version>.sfc (override with OOS_BASE_ROM)." >&2
  echo "" >&2
  echo "Feature flag overrides:" >&2
  echo "  --enable  <csv>   Comma-separated feature names to enable (e.g. water_gate_hooks, ENABLE_WATER_GATE_HOOKS)." >&2
  echo "  --disable <csv>   Comma-separated feature names to disable." >&2
  echo "  --profile <name>  Preset profile (defaults|all-on|all-off) applied before enable/disable lists." >&2
  echo "  --persist-flags   Keep the generated Config/feature_flags.asm (otherwise it is restored after build)." >&2
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
feat_enable=""
feat_disable=""
feat_profile="defaults"
persist_flags=0

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
    --enable)
      feat_enable="${2:-}"
      shift 2
      ;;
    --disable)
      feat_disable="${2:-}"
      shift 2
      ;;
    --profile)
      feat_profile="${2:-defaults}"
      shift 2
      ;;
    --persist-flags)
      persist_flags=1
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
feature_flags_path="$repo_root/Config/feature_flags.asm"

# Optional: temporarily generate Config/feature_flags.asm for this build, then restore.
flags_modified=0
flags_backup=""
restore_flags() {
  if [[ "$flags_modified" != "1" ]]; then
    return 0
  fi
  if [[ "$persist_flags" == "1" ]]; then
    echo "[*] Persisting feature flags: $feature_flags_path"
    return 0
  fi
  if [[ -n "$flags_backup" && -f "$flags_backup" ]]; then
    cp -f "$flags_backup" "$feature_flags_path"
    rm -f "$flags_backup" || true
    echo "[*] Restored feature flags: $feature_flags_path"
  else
    rm -f "$feature_flags_path" || true
    echo "[*] Removed temporary feature flags: $feature_flags_path"
  fi
}
trap restore_flags EXIT

if [[ -n "$feat_enable" || -n "$feat_disable" || "$feat_profile" != "defaults" ]]; then
  if [[ -f "$feature_flags_path" ]]; then
    flags_backup="$(mktemp "$rom_dir/.feature_flags_backup.XXXXXX")"
    cp -f "$feature_flags_path" "$flags_backup"
  fi
  python3 "$repo_root/scripts/set_feature_flags.py" \
    --macros "$repo_root/Util/macros.asm" \
    --output "$feature_flags_path" \
    --profile "$feat_profile" \
    --enable "$feat_enable" \
    --disable "$feat_disable"
  flags_modified=1
fi

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

# Keep water-gate runtime tables synced with Yaze-authored room data.
# Defaults to the ROM declared in Oracle-of-Secrets.yaze (rom_filename),
# then falls back to the selected base ROM.
if [[ "${OOS_SKIP_WATER_TABLE_GEN:-0}" != "1" || "${OOS_SKIP_WATER_FILL_TABLE_GEN:-0}" != "1" ]]; then
  water_table_rom="${OOS_WATER_TABLE_ROM:-}"
  if [[ -z "$water_table_rom" ]]; then
    yaze_project="$repo_root/Oracle-of-Secrets.yaze"
    if [[ -f "$yaze_project" ]]; then
      yaze_rom_rel="$(awk -F= '/^rom_filename=/{print $2; exit}' "$yaze_project" || true)"
      if [[ -n "$yaze_rom_rel" ]]; then
        if [[ "$yaze_rom_rel" = /* ]]; then
          water_table_rom="$yaze_rom_rel"
        else
          water_table_rom="$repo_root/$yaze_rom_rel"
        fi
      fi
    fi
  fi
  if [[ -z "$water_table_rom" || ! -f "$water_table_rom" ]]; then
    water_table_rom="$base_rom"
  fi
  water_table_rom_arg="$water_table_rom"
  if [[ "$water_table_rom_arg" == "$repo_root/"* ]]; then
    water_table_rom_arg="${water_table_rom_arg#$repo_root/}"
  fi
fi

if [[ "${OOS_SKIP_WATER_TABLE_GEN:-0}" != "1" ]]; then
  echo "[*] Generating water-gate runtime tables from: $water_table_rom_arg"
  python3 "$repo_root/scripts/generate_water_gate_runtime_tables.py" --rom "$water_table_rom_arg"
fi

if [[ "${OOS_SKIP_WATER_FILL_TABLE_GEN:-0}" != "1" ]]; then
  echo "[*] Generating water-fill table from custom collision markers: $water_table_rom_arg"
  python3 "$repo_root/scripts/generate_water_fill_table.py" --rom "$water_table_rom_arg"
fi

# Feature-flag guardrails (non-fatal by default).
if ! python3 "$repo_root/scripts/verify_feature_flags.py" --root "$repo_root"; then
  echo "[-] Feature flag verification failed!" >&2
  # Default is non-fatal (developer workflow). Set OOS_FLAGS_FATAL=1 to
  # fail the build when feature flags are inconsistent.
  if [[ "${OOS_FLAGS_FATAL:-0}" == "1" ]]; then
    exit 1
  fi
fi

# Validate Oracle menu registry (bins + component tables) before patching.
if [[ "${OOS_SKIP_MENU_VALIDATE:-0}" != "1" ]]; then
  z3ed_cli="${OOS_Z3ED_BIN:-}"
  if [[ -z "$z3ed_cli" ]]; then
    local_z3ed="$repo_root/../yaze/scripts/z3ed"
    if [[ -x "$local_z3ed" ]]; then
      z3ed_cli="$local_z3ed"
    elif command -v z3ed >/dev/null 2>&1; then
      z3ed_cli="$(command -v z3ed)"
    fi
  fi

  if [[ -n "$z3ed_cli" ]]; then
    echo "[*] Validating Oracle menu registry..."
    menu_validate_args=(oracle-menu-validate --project "$repo_root")
    if [[ "${OOS_MENU_VALIDATE_STRICT:-0}" == "1" ]]; then
      menu_validate_args+=(--strict)
    fi
    if ! "$z3ed_cli" "${menu_validate_args[@]}"; then
      echo "[-] Oracle menu validation failed." >&2
      if [[ "${OOS_MENU_VALIDATE_FATAL:-1}" == "1" ]]; then
        exit 1
      fi
      echo "[-] (Non-fatal: set OOS_MENU_VALIDATE_FATAL=1 to block builds)"
    fi
  else
    echo "[-] Warning: z3ed CLI not found; skipping Oracle menu validation." >&2
  fi
fi

backup_root_default="$HOME/Documents/OracleOfSecrets/Roms"
backup_root="${OOS_BACKUP_ROOT:-$backup_root_default}"
if ! mkdir -p "$backup_root" 2>/dev/null; then
  # Some environments (including sandboxed agents) cannot write to $HOME/Documents.
  # Fall back to a repo-local archive directory so builds remain usable.
  backup_root="$rom_dir/_archives"
  mkdir -p "$backup_root"
  echo "WARNING: backup root not writable; using: $backup_root" >&2
else
  # Some environments can create the directory but disallow file writes.
  if ! tmpfile="$(mktemp "$backup_root/.writetest.XXXXXX" 2>/dev/null)"; then
    backup_root="$rom_dir/_archives"
    mkdir -p "$backup_root"
    echo "WARNING: backup root not writable; using: $backup_root" >&2
  else
    rm -f "$tmpfile" || true
  fi
fi

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

# Generate annotations.json if requested (ASM @watch/@assert tags)
if [[ "${OOS_GENERATE_ANNOTATIONS:-0}" == "1" ]]; then
  annotations_out="$repo_root/.cache/annotations.json"
  python3 "$repo_root/scripts/generate_annotations.py" --root "$repo_root" --out "$annotations_out" || true
fi

# Run static analysis if hooks.json exists
hooks_json="$repo_root/hooks.json"
if [[ -f "$patched_rom" ]]; then
  regen_hooks=0
  if [[ ! -f "$hooks_json" || "${OOS_GENERATE_HOOKS:-0}" == "1" ]]; then
    regen_hooks=1
  elif [[ -f "$repo_root/Config/module_flags.asm" && "$repo_root/Config/module_flags.asm" -nt "$hooks_json" ]]; then
    regen_hooks=1
  elif [[ -f "$repo_root/Config/feature_flags.asm" && "$repo_root/Config/feature_flags.asm" -nt "$hooks_json" ]]; then
    regen_hooks=1
  fi

  if [[ "$regen_hooks" == "1" ]]; then
    echo "[*] Generating hooks.json..."
    python3 "$repo_root/scripts/generate_hooks_json.py" --root "$repo_root" --output "$hooks_json" --rom "$patched_rom" || true
  fi
fi

# Optional validation: ensure hooks.json matches generator output
# Set OOS_VALIDATE_ON_BUILD=1 to run hook + sprite checks non-fatally on every build.
validate_on_build="${OOS_VALIDATE_ON_BUILD:-0}"
if [[ "${OOS_VALIDATE_HOOKS:-0}" == "1" || "$validate_on_build" == "1" ]]; then
  if [[ -f "$hooks_json" && -f "$patched_rom" ]]; then
    if [[ "$validate_on_build" == "1" && "${OOS_VALIDATE_HOOKS:-0}" != "1" ]]; then
      echo "[*] Validating hooks.json (non-fatal)..."
    else
      echo "[*] Validating hooks.json..."
    fi
    python3 "$repo_root/scripts/verify_hooks_json.py" \
      --root "$repo_root" --rom "$patched_rom" --hooks "$hooks_json" || true
  else
    echo "[-] Warning: hooks.json or patched ROM missing; skipping hook validation."
  fi
fi

# Optional validation: sprite registry
if [[ "${OOS_VALIDATE_SPRITES:-0}" == "1" || "$validate_on_build" == "1" ]]; then
  if [[ "$validate_on_build" == "1" && "${OOS_VALIDATE_SPRITES:-0}" != "1" ]]; then
    echo "[*] Validating sprite registry (non-fatal)..."
  else
    echo "[*] Validating sprite registry..."
  fi
  sprite_validate_args=("$repo_root/scripts/validate_sprite_registry.py")
  if [[ "${OOS_VALIDATE_SPRITES_STRICT:-0}" == "1" ]]; then
    sprite_validate_args+=("--strict")
  fi
  python3 "${sprite_validate_args[@]}" || true
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

  if [[ "${SKIP_ANALYSIS:-0}" == "1" ]]; then
    echo "[*] Skipping static analysis (SKIP_ANALYSIS=1)"
  elif [[ -n "$analyzer_script" ]]; then
    # Run static analysis - fail build on errors (warnings are OK unless --strict)
    lint_args=()
    if [[ "$analyzer_script" == *"oracle_analyzer"* ]]; then
      lint_args+=("$patched_rom" --hooks "$hooks_json" --check-hooks --find-mx --find-width-imbalance --check-abi --check-sprite-tables --check-phb-plb --check-jsl-targets --check-rtl-rts)
      # Strict mode: treat warnings as errors (set OOS_LINT_STRICT=1 to enable)
      if [[ "${OOS_LINT_STRICT:-0}" == "1" ]]; then
        lint_args+=(--strict)
      fi
    else
      lint_args+=("$patched_rom" --hooks "$hooks_json")
    fi

    set +e
    python3 "$analyzer_script" "${lint_args[@]}"
    analysis_exit=$?
    set -e

    if [[ $analysis_exit -ne 0 ]]; then
      echo "[-] Static analysis found errors!"
      # Default is non-fatal (developer workflow). Set OOS_ANALYSIS_FATAL=1 to
      # fail the build when the analyzer returns nonzero.
      if [[ "${OOS_ANALYSIS_FATAL:-0}" == "1" ]]; then
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
    if [[ $smoke_exit -eq 2 ]]; then
      echo "[*] Smoke tests skipped (no emulator backend)."
      echo "[*] If you want smoke tests to run/fail: start Mesen2-OOS or set OOS_TEST_REQUIRE_EMULATOR=1."
      echo "[*] (Or pass --skip-tests to silence this message.)"
    else
      echo "[-] Smoke tests failed! Build may be broken."
      # Don't fail the build by default - tests require Mesen2 running
      # Uncomment to make test failures fatal:
      # exit $smoke_exit
    fi
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
