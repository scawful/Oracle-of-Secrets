#!/bin/bash
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") <version> [asar_binary] [--reload] [--no-symbols] [--mesen-sync] [--skip-tests] [--asar=<path>] [--enable <csv>] [--disable <csv>] [--profile <defaults|all-on|all-off>] [--persist-flags] [--help]" >&2
  echo "Base ROM: Roms/oos<version>.sfc (unpatched edit target; override with OOS_BASE_ROM)." >&2
  echo "  Backward compat: Roms/oos<version>_test2.sfc is used only when the standard base is absent." >&2
  echo "" >&2
  echo "Feature flag overrides:" >&2
  echo "  --enable  <csv>   Comma-separated feature names to enable (e.g. water_gate_hooks, ENABLE_WATER_GATE_HOOKS)." >&2
  echo "  --disable <csv>   Comma-separated feature names to disable." >&2
  echo "  --profile <name>  Preset profile (defaults|all-on|all-off) applied before enable/disable lists." >&2
  echo "  --persist-flags   Keep the generated Config/feature_flags.asm (otherwise it is restored after build)." >&2
  echo "Verification: OOS_REQUIRE_CHECKS=analysis,smoke,... requires named checks even when skipped/unavailable." >&2
  echo "  Names: flags,menu,overlap,hooks,sprites,analysis,smoke,annotations." >&2
  echo "  OOS_ANALYZER=<path> selects an analyzer; OOS_TEST_SOCKET=<owned socket> enables exact-ROM current-state smoke." >&2
  echo "  Receipt: Roms/oos<version>x.build.json (override OOS_BUILD_RECEIPT)." >&2
  exit "${1:-1}"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage 0
fi

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
    -h|--help)
      usage 0
      ;;
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

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
rom_dir="$repo_root/Roms"
feature_flags_path="$repo_root/Config/feature_flags.asm"
mkdir -p "$rom_dir"

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
    cp -f "$flags_backup" "$feature_flags_path" || return $?
    rm -f "$flags_backup" || true
    echo "[*] Restored feature flags: $feature_flags_path"
  else
    rm -f "$feature_flags_path" || return $?
    echo "[*] Removed temporary feature flags: $feature_flags_path"
  fi
}


if [[ "$asar_bin" == "z3asm" ]]; then
  local_z3asm="$repo_root/../z3dk/build/src/z3asm/bin/z3asm"
  if [[ -x "$local_z3asm" ]]; then
    asar_bin="$local_z3asm"
  fi
fi

# ROM naming convention:
#   base_rom    = oos${version}.sfc    (unpatched base, the edit target)
#   patched_rom = oos${version}x.sfc   (Asar-patched output, test in emulator)
#
# Backward compat: oos${version}_test2.sfc is accepted when present (transitional
# name used during the ZSCustomOverworld v3 port). Standard is oos${version}.sfc.
default_base="$rom_dir/oos${version}.sfc"
legacy_base="$rom_dir/oos${version}_test2.sfc"
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
patched_rom="$rom_dir/oos${version}x.sfc"
symbols_rel="Roms/oos${version}x.sym"
symbols_path="$rom_dir/oos${version}x.sym"
mlb_rel="Roms/oos${version}x.mlb"
mlb_path="$rom_dir/oos${version}x.mlb"

source "$repo_root/Scripts/Build/build_checks.sh"
init_build_receipt
current_stage="base_rom"

if [[ ! -f "$base_rom" ]]; then
  echo "ERROR: Base ROM not found: $base_rom" >&2
  exit 1
fi
if [[ "$base_rom" != /* ]]; then
  base_rom="$(cd "$(dirname "$base_rom")" && pwd -P)/$(basename "$base_rom")"
fi

if [[ -f "$legacy_base" && "$base_rom" != "$legacy_base" ]]; then
  echo "NOTE: Ignoring legacy base ROM $legacy_base; using $base_rom" >&2
fi
if [[ "$base_rom" -ef "$patched_rom" ]]; then
  echo "ERROR: Base ROM and patched output refer to the same file; refusing to patch the edit target." >&2
  exit 1
fi
echo "Using base ROM: $base_rom"

if [[ -n "$feat_enable" || -n "$feat_disable" || "$feat_profile" != "defaults" ]]; then
  if [[ -f "$feature_flags_path" ]]; then
    flags_backup="$(mktemp "$rom_dir/.feature_flags_backup.XXXXXX")"
    cp -f "$feature_flags_path" "$flags_backup"
  fi
  flags_modified=1
  current_stage="feature_generation"
  python3 "$repo_root/Scripts/Build/set_feature_flags.py" \
    --macros "$repo_root/Util/macros.asm" \
    --output "$feature_flags_path" \
    --profile "$feat_profile" \
    --enable "$feat_enable" \
    --disable "$feat_disable"
fi


# Custom collision is editor-authored but source-owned. Fail before generating
# build inputs when the selected base ROM does not reproduce the tracked JSON.
echo "[*] Validating custom collision source contract..."
run_check collision_source 1 python3 "$repo_root/Scripts/Generate/validate_custom_collision_source.py" \
  --root "$repo_root" \
  --rom "$base_rom"

# Expanded messages are source-owned. Fail before generating any build inputs
# when the canonical bundle and tracked Asar include have drifted.
echo "[*] Validating expanded message source contract..."
run_check message_source 1 python3 "$repo_root/Scripts/Generate/validate_expanded_message_source.py" \
  --root "$repo_root"

current_stage="output_snapshot"
snapshot_build_outputs

# Keep water-gate runtime tables synced with the validated editor-authored base
# ROM. The tracked custom-collision source contract guarantees that marker
# tiles ($F5) are present there, so never implicitly reuse stale patched output.
# OOS_WATER_TABLE_ROM remains an explicit diagnostic override.
if [[ "${OOS_SKIP_WATER_TABLE_GEN:-0}" != "1" || "${OOS_SKIP_WATER_FILL_TABLE_GEN:-0}" != "1" ]]; then
  water_table_rom="${OOS_WATER_TABLE_ROM:-$base_rom}"
  if [[ "$water_table_rom" != /* ]]; then
    water_table_rom="$repo_root/$water_table_rom"
  fi
  if [[ ! -f "$water_table_rom" ]]; then
    echo "ERROR: Water-table source ROM not found: $water_table_rom" >&2
    exit 1
  fi
  receipt artifact --name water_source_rom --path "$water_table_rom"
  water_table_rom_arg="$water_table_rom"
  if [[ "$water_table_rom_arg" == "$repo_root/"* ]]; then
    water_table_rom_arg="${water_table_rom_arg#$repo_root/}"
  fi
fi

if [[ "${OOS_SKIP_WATER_TABLE_GEN:-0}" != "1" ]]; then
  echo "[*] Generating water-gate runtime tables from: $water_table_rom_arg"
  generate_water_gate_tables() {
    (
      cd "$repo_root"
      python3 "$repo_root/Scripts/Generate/generate_water_gate_runtime_tables.py" \
        --rom "$water_table_rom_arg" \
        --out-asm "$repo_root/Dungeons/generated/water_gate_runtime_tables.asm"
    )
  }
  run_check water_tables 1 generate_water_gate_tables
else
  omit_check water_tables skipped 0 "OOS_SKIP_WATER_TABLE_GEN=1; tracked generated input retained"
fi

if [[ "${OOS_SKIP_WATER_FILL_TABLE_GEN:-0}" != "1" ]]; then
  echo "[*] Generating water-fill table from custom collision markers: $water_table_rom_arg"
  generate_water_fill_tables() {
    (
      cd "$repo_root"
      python3 "$repo_root/Scripts/Generate/generate_water_fill_table.py" \
        --rom "$water_table_rom_arg" \
        --out-asm "$repo_root/Dungeons/generated/water_fill_table.asm"
    )
  }
  run_check water_fill 1 generate_water_fill_tables
else
  omit_check water_fill skipped 0 "OOS_SKIP_WATER_FILL_TABLE_GEN=1; tracked generated input retained"
fi

# Profile consistency is required by default; diagnostic opt-outs remain visible.
run_check flags "$(check_required flags "${OOS_FLAGS_FATAL:-1}")" \
  python3 "$repo_root/Scripts/Build/verify_feature_flags.py" --root "$repo_root" --strict

menu_required="$(check_required menu "${OOS_MENU_VALIDATE_FATAL:-1}")"
if [[ "${OOS_SKIP_MENU_VALIDATE:-0}" == "1" ]]; then
  # An explicit diagnostic skip may disable the default, never an explicit requirement.
  omit_check menu skipped "$(check_required menu "${OOS_MENU_VALIDATE_FATAL:-0}")" "OOS_SKIP_MENU_VALIDATE=1"
else
  z3ed_cli="${OOS_Z3ED_BIN:-}"
  if [[ -z "$z3ed_cli" ]]; then
    local_z3ed="$repo_root/../yaze/scripts/z3ed"
    if [[ -x "$local_z3ed" ]]; then
      z3ed_cli="$local_z3ed"
    elif command -v z3ed >/dev/null 2>&1; then
      z3ed_cli="$(command -v z3ed)"
    fi
  fi
  if [[ -n "$z3ed_cli" ]] && command -v "$z3ed_cli" >/dev/null 2>&1; then
    receipt tool --name z3ed --path "$(command -v "$z3ed_cli")"
    menu_validate_args=(oracle-menu-validate --project "$repo_root")
    if [[ "${OOS_MENU_VALIDATE_STRICT:-0}" == "1" ]]; then menu_validate_args+=(--strict); fi
    run_check menu "$menu_required" "$z3ed_cli" "${menu_validate_args[@]}"
  else
    omit_check menu unavailable "$menu_required" "z3ed CLI not found"
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

# GM-005: Sanity check — verify the custom collision region in the base ROM
# and the previously built patched ROM are still in sync.
#
# Correct workflow: edits are always made to oos<version>.sfc (the
# unpatched base ROM).  oos<version>x.sfc is build output only and is never
# edited directly.  This check catches the rare case where a tool (e.g. a
# mistargeted z3ed --write invocation) wrote to the patched ROM instead.
#
# Set OOS_ALLOW_EDIT_OVERWRITE=1 to bypass (use with caution).
current_stage="collision_overwrite_guard"
if [[ -f "$patched_rom" && -f "$base_rom" ]]; then
  if ! python3 - "$base_rom" "$patched_rom" << 'PY_GUARD'
import sys
COLLISION_START = 0x128090
COLLISION_END   = 0x12E000
base    = open(sys.argv[1], 'rb').read()
patched = open(sys.argv[2], 'rb').read()
if COLLISION_START >= min(len(base), len(patched)):
    sys.exit(0)  # region not present in at least one ROM — nothing to check
chunk_base    = base[COLLISION_START:min(COLLISION_END, len(base))]
chunk_patched = patched[COLLISION_START:min(COLLISION_END, len(patched))]
# Pad shorter chunk to equal length for byte-level comparison
maxlen = max(len(chunk_base), len(chunk_patched))
chunk_base    = chunk_base.ljust(maxlen, b'\x00')
chunk_patched = chunk_patched.ljust(maxlen, b'\x00')
sys.exit(0 if chunk_base == chunk_patched else 1)
PY_GUARD
  then
    echo "" >&2
    echo "WARNING (GM-005): Custom collision data in '$(basename "$patched_rom")' unexpectedly" >&2
    echo "  differs from '$(basename "$base_rom")'." >&2
    echo "  Edits should always target the base ROM ($(basename "$base_rom")); the patched" >&2
    echo "  ROM is build output only and should not be edited directly." >&2
    echo "  Something may have written to '$(basename "$patched_rom")' outside the build pipeline" >&2
    echo "  (e.g. a z3ed --write command pointed at the wrong ROM)." >&2
    echo "  Proceeding will discard whatever is in '$(basename "$patched_rom")' and rebuild from base." >&2
    echo "" >&2
    if [[ "${OOS_ALLOW_EDIT_OVERWRITE:-0}" != "1" ]]; then
      echo "ERROR: Aborting.  Investigate the divergence, then set OOS_ALLOW_EDIT_OVERWRITE=1 to override." >&2
      exit 1
    fi
    echo "WARNING: OOS_ALLOW_EDIT_OVERWRITE=1 — proceeding." >&2
  fi
fi

current_stage="assembler_available"
if ! resolved_asar_bin="$(command -v "$asar_bin")"; then
  echo "ERROR: assembler not found: $asar_bin" >&2
  exit 1
fi
if [[ "$resolved_asar_bin" != /* ]]; then
  resolved_asar_bin="$(cd "$(dirname "$resolved_asar_bin")" && pwd -P)/$(basename "$resolved_asar_bin")"
fi
asar_bin="$resolved_asar_bin"

receipt tool --name assembler --path "$(command -v "$asar_bin")"
receipt tool --name python --path "$(command -v python3)"

current_stage="prepare_output"
cp -f "$base_rom" "$patched_rom"

# Stamp Config/version.json into the in-game version line (message $C7) before
# assembly. z3asm records the final output ROM hash in hooks.json, so post-build
# stamping would invalidate the exact-span provenance used by the manifest.
if [[ "${OOS_SKIP_VERSION_STAMP:-0}" != "1" ]]; then
  run_check version_stamp 1 python3 "$repo_root/Scripts/Build/version_stamp.py" --rom "$patched_rom"
else
  omit_check version_stamp skipped 0 "OOS_SKIP_VERSION_STAMP=1"
fi

current_stage="source_snapshot"
receipt snapshot --phase pre_assembly

# z3asm writes hooks.json from the bytes it assembles (see z3dk docs/Z3DK_HOOKS.md).
hooks_json="$repo_root/Roms/hooks.json"
assembler_emits=()
# Never accept symbols or hook metadata left by a prior build at these paths.
rm -f "$hooks_json" "$symbols_path" "$mlb_path"
current_stage="assembly"
if [[ "$asar_bin" == *"z3asm"* ]]; then
  assembler_emits+=("--emit=sourcemap:$repo_root/Roms/sourcemap.json" "--emit=hooks:$hooks_json")
fi

assemble_rom() {
  if [[ $emit_symbols -eq 1 ]]; then
    (
      cd "$repo_root"
      "$asar_bin" --symbols=wla --symbols-path="$symbols_path" ${assembler_emits[@]+"${assembler_emits[@]}"} Oracle_main.asm "$patched_rom"
    )
  else
    (
      cd "$repo_root"
      "$asar_bin" ${assembler_emits[@]+"${assembler_emits[@]}"} Oracle_main.asm "$patched_rom"
    )
  fi
}
run_check assembly 1 assemble_rom

receipt artifact --name output_rom --path "$patched_rom"
if [[ "$emit_symbols" == "1" ]]; then
  receipt artifact --name symbols --path "$symbols_path"
fi
# Asar metadata is rebuilt from the active include graph on every build.
if [[ "$asar_bin" != *"z3asm"* ]]; then
  run_check hooks_generation 1 python3 "$repo_root/Scripts/Generate/generate_hooks_json.py" \
    --root "$repo_root" --output "$hooks_json" --rom "$patched_rom"
fi
run_check hooks 1 python3 "$repo_root/Scripts/Validate/verify_hooks_json.py" \
  --root "$repo_root" --rom "$patched_rom" --hooks "$hooks_json" --identity-only
receipt artifact --name hooks --path "$hooks_json"
echo "Assembled patched ROM: $patched_rom"

# Refresh the ignored Yaze integration manifest from the exact source and ROM
# that produced this build. Fail closed so source-sync never opens against a
# missing or stale allocation contract.
echo "[*] Generating Yaze hack manifest..."
manifest_args=(
  --root "$repo_root"
  --output "$repo_root/Roms/hack_manifest.json"
  --dev-rom "$base_rom"
  --rom "$patched_rom"
)
if [[ -n "${OOS_MANIFEST_ROOT:-}" ]]; then
  manifest_root="$OOS_MANIFEST_ROOT"
  if [[ "$manifest_root" != /* ]]; then
    manifest_root="$(cd "$manifest_root" && pwd -P)"
  fi
  manifest_args+=(--manifest-root "$manifest_root")
fi
# z3asm: exact spans from the hooks.json this build just emitted; the
# generator rejects it unless its recorded ROM hash matches $patched_rom.
# asar: explicit source-scan fallback with estimated sizes.
# Legacy SHA-1-only z3asm metadata passes the identity gate above, but the
# exact-span manifest contract requires SHA-256. Its fallback remains explicitly
# estimated. Missing or mismatched digests have already failed closed.
if [[ "$asar_bin" == *"z3asm"* ]] &&
  python3 -c 'import json,re,sys; value=json.load(open(sys.argv[1])).get("rom",{}).get("sha256"); sys.exit(0 if isinstance(value,str) and re.fullmatch(r"[0-9a-f]{64}",value) else 1)' "$hooks_json"
then
  manifest_hook_args=(--hooks "$hooks_json")
else
  if [[ "$asar_bin" == *"z3asm"* ]]; then
    echo "[-] z3asm hooks.json has validated legacy SHA-1 but no SHA-256; using estimated source-scan manifest fallback." >&2
  fi
  manifest_hook_args=(--hook-source python-scan)
fi
run_check manifest 1 python3 "$repo_root/Scripts/Generate/generate_hack_manifest.py" \
  "${manifest_args[@]}" \
  "${manifest_hook_args[@]}"

receipt artifact --name manifest --path "$repo_root/Roms/hack_manifest.json"

# Export symbols for yaze + Mesen2.
if [[ $emit_symbols -eq 1 && -f "$symbols_path" ]]; then
  export_args=("$symbols_path" "-o" "$mlb_path" "--rom-name" "oos${version}x" "--filter" "oracle")
  if [[ $mesen_sync -eq 1 ]]; then
    export_args+=("--sync")
  fi
  run_check symbol_export 1 python3 "$repo_root/Scripts/Generate/export_symbols.py" "${export_args[@]}"
  receipt artifact --name mlb --path "$mlb_path"
fi

# Run ZScream overlap check
if [[ $emit_symbols -eq 1 ]]; then
  run_check overlap 1 python3 "$repo_root/Scripts/Build/check_zscream_overlap.py" --symbols "$symbols_path"
else
  omit_check overlap skipped "$(check_required overlap 0)" "--no-symbols requested; no fresh emission map"
fi

# Generate annotations.json if requested (ASM @watch/@assert tags)
if [[ "${OOS_GENERATE_ANNOTATIONS:-0}" == "1" || "$(check_required annotations 0)" == "1" ]]; then
  annotations_out="$repo_root/.cache/annotations.json"
  run_check annotations 1 python3 "$repo_root/Scripts/Generate/generate_annotations.py" --root "$repo_root" --out "$annotations_out"
  receipt artifact --name annotations --path "$annotations_out"
fi

validate_on_build="${OOS_VALIDATE_ON_BUILD:-0}"
if [[ "$asar_bin" != *"z3asm"* && ( "${OOS_VALIDATE_HOOKS:-0}" == "1" || "$validate_on_build" == "1" ) ]]; then
  run_check hooks_source 1 python3 "$repo_root/Scripts/Validate/verify_hooks_json.py" \
    --root "$repo_root" --rom "$patched_rom" --hooks "$hooks_json"
fi
if [[ "${OOS_VALIDATE_SPRITES:-0}" == "1" || "$validate_on_build" == "1" || "$(check_required sprites 0)" == "1" ]]; then
  sprite_validate_args=("$repo_root/Scripts/Validate/validate_sprite_registry.py")
  if [[ "${OOS_VALIDATE_SPRITES_STRICT:-0}" == "1" ]]; then sprite_validate_args+=(--strict); fi
  run_check sprites 1 python3 "${sprite_validate_args[@]}"
fi

analysis_required="$(check_required analysis "${OOS_ANALYSIS_FATAL:-0}")"
analyzer_script="${OOS_ANALYZER:-}"
if [[ -z "$analyzer_script" ]]; then
  for candidate in "$repo_root/../z3dk/scripts/oracle_analyzer.py" "$repo_root/../z3dk/scripts/static_analyzer.py"; do
    if [[ -f "$candidate" ]]; then analyzer_script="$candidate"; break; fi
  done
fi
if [[ "${SKIP_ANALYSIS:-0}" == "1" ]]; then
  omit_check analysis skipped "$analysis_required" "SKIP_ANALYSIS=1"
elif [[ -z "$analyzer_script" || ! -f "$analyzer_script" ]]; then
  omit_check analysis unavailable "$analysis_required" "Analyzer missing; set OOS_ANALYZER explicitly in isolated copies"
elif [[ "$emit_symbols" != "1" || ! -f "$symbols_path" ]]; then
  omit_check analysis unavailable "$analysis_required" "Fresh symbols required; --no-symbols cannot use another build's symbols"
else
  receipt tool --name analyzer --path "$analyzer_script"
  lint_args=("$patched_rom" --hooks "$hooks_json")
  if [[ "$analyzer_script" == *"oracle_analyzer"* ]]; then
    lint_args+=(--sym "$symbols_path" --check-hooks --find-mx --find-width-imbalance --check-abi --check-sprite-tables --check-phb-plb --check-jsl-targets --check-rtl-rts)
    if [[ "${OOS_LINT_STRICT:-0}" == "1" ]]; then lint_args+=(--strict); fi
  fi
  if [[ "$analyzer_script" != /* ]]; then
    analyzer_script="$(cd "$(dirname "$analyzer_script")" && pwd -P)/$(basename "$analyzer_script")"
  fi
  run_analyzer() {
    (
      cd "$repo_root"
      python3 "$analyzer_script" "${lint_args[@]}"
    )
  }
  run_check analysis "$analysis_required" run_analyzer
fi

# Runtime checks only use an explicitly selected endpoint and the exact ROM.
smoke_required="$(check_required smoke "${OOS_TEST_REQUIRE_EMULATOR:-0}")"
if [[ "$skip_tests" == "1" || "${SKIP_TESTS:-0}" == "1" ]]; then
  omit_check smoke skipped "$smoke_required" "skip-tests requested"
elif [[ -z "${OOS_TEST_SOCKET:-}" ]]; then
  omit_check smoke unavailable "$smoke_required" "No OOS_TEST_SOCKET; no emulator autodiscovery attempted"
else
  current_stage="smoke"
  smoke_report="$rom_dir/oos${version}x.smoke.json"
  if python3 "$repo_root/Scripts/Build/run_build_smoke.py" --rom "$patched_rom" --socket "$OOS_TEST_SOCKET" > "$smoke_report"; then
    receipt artifact --name smoke_report --path "$smoke_report"
    cat "$smoke_report"
    record_check smoke passed "$smoke_required" "Exact ROM identity verified before and after current-state smoke"
  else
    smoke_exit=$?
    receipt artifact --name smoke_report --path "$smoke_report"
    cat "$smoke_report"
    if [[ "$smoke_exit" == "2" ]]; then
      omit_check smoke unavailable "$smoke_required" "Explicit smoke endpoint/backend unavailable"
    else
      record_check smoke failed 1 "Smoke failed or exact ROM identity could not be established" "$smoke_exit"
      exit "$smoke_exit"
    fi
  fi
fi

if [[ $reload -eq 1 ]]; then
  # Legacy --reload means reset, not loading a different ROM. Require the same
  # explicit, non-protected endpoint and current artifact before any command.
  if [[ -z "${OOS_TEST_SOCKET:-}" ]]; then
    omit_check reload unavailable 1 "--reload requires OOS_TEST_SOCKET; no autodiscovery attempted"
  fi
  reload_report="$rom_dir/oos${version}x.reload-identity.json"
  current_stage="reload_identity"
  if python3 "$repo_root/Scripts/Build/run_build_smoke.py" --rom "$patched_rom" --socket "$OOS_TEST_SOCKET" --verify-only > "$reload_report"; then
    receipt artifact --name reload_identity --path "$reload_report"
    record_check reload_identity passed 1 "Explicit endpoint already runs the exact artifact"
  else
    reload_exit=$?
    receipt artifact --name reload_identity --path "$reload_report"
    cat "$reload_report"
    record_check reload_identity failed 1 "Reset refused: exact endpoint identity not established" "$reload_exit"
    exit "$reload_exit"
  fi
  run_check reload 1 env MESEN_AUTO_FOCUS=0 MESEN_AUTO_UNSTASH=0 MESEN_AUTO_STASH=0 MESEN_STASH_ON_FAIL=0 \
    python3 "$repo_root/Scripts/Mesen2/mesen2_client.py" --socket "$OOS_TEST_SOCKET" reset
fi

current_stage="complete"
