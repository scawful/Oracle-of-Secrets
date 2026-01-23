#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Install the Mesen2 OOS app bundle via the forked Mesen2 install script.

Usage: mesen2_install_app.sh [options]

Options:
  --src PATH       Source app bundle (defaults to fork publish output)
  --dest PATH      Destination directory or .app path
  --name NAME      Destination app name (default: Mesen2 OOS.app)
  --user           Install to ~/Applications
  --prune          Move other Mesen app bundles in DEST to backup
  --no-backup      Replace without backing up existing bundle(s)
  --force          Alias for --no-backup
  --symlink        Create/refresh Mesen.app -> installed app in DEST
  --symlink-force  Replace existing Mesen.app if needed
  --dry-run        Print actions without copying
  -h, --help       Show this help

Env:
  MESEN_APP_SRC    Override source app bundle
  MESEN_APP_DEST   Override destination directory or .app path
  MESEN_APP_NAME   Override destination app name
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FORK_INSTALL="${REPO_ROOT}/../third_party/forks/Mesen2/tools/install_mesen2_oos.sh"

if [[ ! -x "${FORK_INSTALL}" ]]; then
  echo "Missing fork install script: ${FORK_INSTALL}" >&2
  echo "Make sure the Mesen2 fork is checked out and built." >&2
  exit 1
fi

ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --src)
      ARGS+=(--source "$2")
      shift 2
      ;;
    --dest)
      ARGS+=(--dest "$2")
      shift 2
      ;;
    --name)
      ARGS+=(--name "$2")
      shift 2
      ;;
    --user|--prune|--no-backup|--force|--symlink|--symlink-force|--dry-run)
      ARGS+=("$1")
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

exec "${FORK_INSTALL}" "${ARGS[@]}"
