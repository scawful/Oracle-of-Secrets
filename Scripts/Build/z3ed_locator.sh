# Locate the z3ed CLI for build stages. Sourced by build_rom.sh.
#
# Order: OOS_Z3ED_BIN (override, returned as given), the sibling yaze checkout,
# PATH, the Yaze Nightly current release bundle, then ~/.local/yaze. A GUI
# launch (yaze Build/Run) often has a PATH without ~/.local/bin, so the
# install locations are checked directly.
#
# Prints the selected path on stdout and returns 0, or prints the checked
# locations on stderr and returns 1.
oos_find_z3ed() {
  local repo="${1:-}"
  if [[ -n "${OOS_Z3ED_BIN:-}" ]]; then
    printf '%s\n' "$OOS_Z3ED_BIN"
    return 0
  fi

  local yaze_home="${OOS_YAZE_HOME:-$HOME/.local/yaze}"
  local nightly_app="${OOS_YAZE_NIGHTLY_APP:-$HOME/Applications/Yaze Nightly.app}"
  local candidates=()
  if [[ -n "$repo" ]]; then
    candidates+=("$repo/../yaze/scripts/z3ed")
  fi
  local on_path
  on_path="$(command -v z3ed 2>/dev/null || true)"
  if [[ -n "$on_path" ]]; then
    candidates+=("$on_path")
  fi
  candidates+=("$nightly_app/Contents/MacOS/z3ed")
  if [[ -d "$nightly_app" ]]; then
    # The Nightly app is a symlink into the release folder that also holds z3ed.
    local app_real
    app_real="$(cd "$nightly_app" 2>/dev/null && pwd -P || true)"
    if [[ -n "$app_real" ]]; then
      candidates+=("$(dirname "$app_real")/z3ed")
    fi
  fi
  candidates+=("$yaze_home/nightly/current/z3ed" "$yaze_home/bin/z3ed" "$yaze_home/z3ed")

  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" && -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  {
    echo "ERROR: z3ed not found. Checked OOS_Z3ED_BIN (unset), then:"
    if [[ -z "$on_path" ]]; then
      echo "  PATH: no z3ed"
    fi
    for candidate in "${candidates[@]}"; do
      echo "  $candidate"
    done
    echo "Install Yaze Nightly or set OOS_Z3ED_BIN to a z3ed binary."
  } >&2
  return 1
}
