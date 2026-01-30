#!/bin/bash
# Thin wrapper: run test suites via test_runner.py.
#
# Usage:
#   ./scripts/run_regression_tests.sh [suite] [options]
#
# Suites: smoke (default) | regression | full
# Options: --quick (=smoke) --full --tag TAG -q|--quiet -v|--verbose --fail-fast
#          --moe | --no-moe --junit | --json
#
# Env: MESEN2_SOCKET_PATH, OOS_TEST_BACKEND, OOS_MOE_ENABLED

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$REPO_ROOT/tests/manifest.json"

SUITE="smoke"
ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    smoke|regression|full) SUITE="$1"; shift ;;
    --quick) SUITE=smoke; shift ;;
    --full)  SUITE=full; shift ;;
    --moe)   ARGS+=(--moe-enabled); shift ;;
    --no-moe) shift ;;
    -q|--quiet)   ARGS+=(-q); shift ;;
    --verbose|-v) ARGS+=(-v); shift ;;
    --junit) ARGS+=(--output-format junit); shift ;;
    --json)  ARGS+=(--output-format json); shift ;;
    --tag)   ARGS+=("--tag" "$2"); shift 2 ;;
    --fail-fast) ARGS+=(--fail-fast); shift ;;
    --help|-h)
      echo "Usage: $0 [smoke|regression|full] [--tag TAG] [-q|--quiet] [-v|--verbose] [--fail-fast] [--moe|--no-moe] [--junit|--json]"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

ARGS=("--suite" "$SUITE" "--manifest" "$MANIFEST" "${ARGS[@]}")

# MoE default from env
if [[ "${OOS_MOE_ENABLED:-1}" == "1" ]]; then
  ARGS+=(--moe-enabled)
fi

cd "$REPO_ROOT"
if [[ ! -f "$MANIFEST" ]]; then
  echo "Error: manifest not found: $MANIFEST"
  exit 1
fi

exec python3 scripts/test_runner.py "${ARGS[@]}"
