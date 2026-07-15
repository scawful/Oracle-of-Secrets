#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Fast Oracle build + reload + validate wrapper.

Usage:
  Scripts/Build/oos-verify.sh [version] [extra dev_loop args]

Examples:
  Scripts/Build/oos-verify.sh
  Scripts/Build/oos-verify.sh 168 --z3asm
  Scripts/Build/oos-verify.sh --skip-tests
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

exec "${ROOT_DIR}/Scripts/Build/dev_loop.sh" "${version}" --mesen-sync --reload --validate "$@"
