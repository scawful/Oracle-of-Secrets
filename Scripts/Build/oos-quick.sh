#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Fast Oracle build + reload wrapper.

Usage:
  Scripts/oos-quick.sh [version] [extra dev_loop args]

Examples:
  Scripts/oos-quick.sh
  Scripts/oos-quick.sh 168 --z3asm
  Scripts/oos-quick.sh --skip-tests
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

version="168"

if [[ $# -gt 0 ]]; then
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    ''|*[!0-9]*)
      ;;
    *)
      version="$1"
      shift
      ;;
  esac
fi

exec "${ROOT_DIR}/Scripts/Build/dev_loop.sh" "${version}" --mesen-sync --reload "$@"
