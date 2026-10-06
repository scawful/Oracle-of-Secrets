# Build-stage policy shared by build_rom.sh and its subprocess fixtures.
# Sourced after paths and restore_flags have been defined; does not run checks.

receipt_tool="$repo_root/Scripts/Build/build_receipt.py"
receipt_path="${OOS_BUILD_RECEIPT:-$rom_dir/oos${version}x.build.json}"
required_checks="${OOS_REQUIRE_CHECKS:-}"
current_stage="preflight"
receipt_started=0

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

finish_build() {
  local code=$? finish_code=0 restore_code=0
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
    echo "Build receipt: $receipt_path"
  fi
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
