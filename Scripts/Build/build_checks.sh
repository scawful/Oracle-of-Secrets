# Build-stage policy shared by build_rom.sh and its subprocess fixtures.
# Sourced after paths and restore_flags have been defined; does not run checks.

receipt_tool="$repo_root/Scripts/Build/build_receipt.py"
receipt_path="${OOS_BUILD_RECEIPT:-$rom_dir/oos${version}x.build.json}"
required_checks="${OOS_REQUIRE_CHECKS:-}"
current_stage="preflight"
receipt_started=0
build_output_backup=""
build_output_transaction=0
build_output_paths=()
build_output_existed=()

receipt() {
  python3 "$receipt_tool" "$1" --receipt "$receipt_path" "${@:2}"
}

check_required() {
  case ",$required_checks," in
    *,"$1",*) printf '1' ;;
    *) printf '%s' "$2" ;;
  esac
}

record_check() {
  receipt check --name "$1" --status "$2" --required "$3" --detail "$4" --exit-code "${5:-0}"
}

run_check() {
  local name="$1" required="$2" code=0
  shift 2
  current_stage="$name"
  if "$@"; then
    record_check "$name" passed "$required" "Command completed successfully"
  else
    code=$?
    record_check "$name" failed "$required" "Command returned $code" "$code"
    echo "[-] $name failed (exit $code; required=$required)." >&2
    if [[ "$required" == "1" ]]; then return "$code"; fi
  fi
}

omit_check() {
  local name="$1" status="$2" required="$3" detail="$4"
  current_stage="$name"
  record_check "$name" "$status" "$required" "$detail"
  echo "[-] $name: $status ($detail; required=$required)." >&2
  if [[ "$required" == "1" ]]; then return 1; fi
}

snapshot_build_outputs() {
  # Only derived files belong to this transaction. Keep the base ROM, authored
  # source, receipt and diagnostic reports outside it.
  build_output_paths=(
    "$patched_rom" "$symbols_path" "$mlb_path"
    "$rom_dir/hooks.json" "$rom_dir/hack_manifest.json" "$rom_dir/sourcemap.json"
    "$repo_root/.cache/annotations.json"
    "$repo_root/Dungeons/generated/water_gate_runtime_tables.asm"
    "$repo_root/Dungeons/generated/water_fill_table.asm"
  )
  local path index
  for path in "${build_output_paths[@]}"; do
    if [[ -L "$path" || ( -e "$path" && ! -f "$path" ) ]]; then
      echo "ERROR: Managed build output must be a regular file: $path" >&2
      return 1
    fi
  done
  build_output_backup="$(mktemp -d "$rom_dir/.build-outputs.XXXXXX")" || return $?
  for index in "${!build_output_paths[@]}"; do
    path="${build_output_paths[$index]}"
    if [[ -f "$path" ]]; then
      cp -p "$path" "$build_output_backup/$index" || return $?
      build_output_existed+=(1)
    else
      build_output_existed+=(0)
    fi
  done
  build_output_transaction=1
}

restore_build_outputs() {
  local path index temporary code=0
  for index in "${!build_output_paths[@]}"; do
    path="${build_output_paths[$index]}"
    if [[ "${build_output_existed[$index]}" == "1" ]]; then
      if [[ -d "$path" && ! -L "$path" ]]; then
        echo "ERROR: Cannot restore a file over an output directory: $path" >&2
        code=1
        continue
      fi
      if [[ -L "$path" ]]; then
        rm -f "$path" || { code=1; continue; }
      fi
      # Replace the file only after its complete prior contents are available.
      # In particular, do not follow a link created at an output path mid-build.
      temporary="$(mktemp "${path}.restore.XXXXXX")" || { code=1; continue; }
      if ! cp -p "$build_output_backup/$index" "$temporary" ||
         ! mv -f "$temporary" "$path"; then
        rm -f "$temporary"
        code=1
      fi
    elif ! rm -f "$path"; then
      code=1
    fi
  done
  return "$code"
}

finish_build() {
  local code=$? finish_code=0 restore_code=0 rollback_code=0
  trap - EXIT
  set +e
  restore_flags
  restore_code=$?
  if [[ "$receipt_started" == "1" ]]; then
    if [[ "$restore_code" != "0" ]]; then
      record_check flags_restore failed 1 "Unable to restore feature flags" "$restore_code"
      code="$restore_code"
    fi
    if [[ "$code" != "0" ]]; then
      record_check "$current_stage" failed 1 "Build stopped at this stage" "$code"
    fi
    receipt finish --exit-code "$code" --stage "$current_stage"
    finish_code=$?
    if [[ "$finish_code" != "0" ]]; then code="$finish_code"; fi
  fi
  # Finalize against the attempted build before restoring its files. This also
  # catches failures found only by final source/artifact identity verification.
  if [[ "$code" != "0" && "$build_output_transaction" == "1" ]]; then
    restore_build_outputs
    rollback_code=$?
    if [[ "$rollback_code" == "0" ]]; then
      record_check output_rollback passed 1 \
        "Failed build outputs restored to their pre-build state; files absent before remain absent. Artifact hashes describe the failed attempt, not the restored paths."
      echo "[*] Restored pre-build outputs and generated water includes after failure." >&2
    else
      record_check output_rollback failed 1 \
        "Output restoration incomplete; recover prior files from $build_output_backup. Artifact hashes describe the failed attempt." "$rollback_code"
      echo "ERROR: Output restoration incomplete; backups retained at $build_output_backup" >&2
    fi
  fi
  if [[ -n "$build_output_backup" && "$rollback_code" == "0" ]]; then
    rm -rf "$build_output_backup"
  fi
  if [[ "$receipt_started" == "1" ]]; then echo "Build receipt: $receipt_path"; fi
  exit "$code"
}

init_build_receipt() {
  receipt init --root "$repo_root" --base-rom "$base_rom" --version "$version" \
    --requested-profile "$feat_profile;enable=$feat_enable;disable=$feat_disable;persist=$persist_flags" \
    --assembler "$asar_bin"
  receipt_started=1
  trap finish_build EXIT
  local name
  local old_ifs="$IFS"
  IFS=,
  for name in $required_checks; do
    case "$name" in
      flags|menu|overlap|hooks|sprites|analysis|smoke|annotations) ;;
      *) echo "ERROR: unknown OOS_REQUIRE_CHECKS entry: $name" >&2; IFS="$old_ifs"; return 1 ;;
    esac
  done
  IFS="$old_ifs"
}
