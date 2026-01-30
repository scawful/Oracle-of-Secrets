#!/bin/bash
# run_regression_tests.sh - Wrapper for running regression test suites
#
# Usage:
#   ./scripts/run_regression_tests.sh [suite] [options]
#
# Suites:
#   smoke       - Quick validation tests (<1 min)
#   regression  - Known bug regression tests (<10 min)
#   full        - All tests
#
# Options:
#   --quick     - Alias for smoke suite
#   --full      - Alias for full suite
#   --moe       - Enable MoE analysis on failure
#   --no-moe    - Disable MoE analysis
#   --verbose   - Verbose output
#   --junit     - Output JUnit XML format
#   --json      - Output JSON format
#   --tag TAG   - Run tests matching tag
#   --fail-fast - Stop on first failure
#
# Environment:
#   MESEN2_SOCKET_PATH  - Override Mesen2 socket path
#   OOS_TEST_BACKEND    - Force backend (socket/yaze/cli)
#   OOS_MOE_ENABLED     - Enable MoE analysis (default: 1)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Defaults
SUITE="smoke"
MOE_ENABLED="${OOS_MOE_ENABLED:-1}"
VERBOSE=""
OUTPUT_FORMAT="text"
TAG=""
FAIL_FAST=""
MANIFEST="$PROJECT_ROOT/tests/manifest.json"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        smoke|regression|full)
            SUITE="$1"
            shift
            ;;
        --quick)
            SUITE="smoke"
            shift
            ;;
        --full)
            SUITE="full"
            shift
            ;;
        --moe)
            MOE_ENABLED=1
            shift
            ;;
        --no-moe)
            MOE_ENABLED=0
            shift
            ;;
        --verbose|-v)
            VERBOSE="-v"
            shift
            ;;
        --junit)
            OUTPUT_FORMAT="junit"
            shift
            ;;
        --json)
            OUTPUT_FORMAT="json"
            shift
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        --fail-fast)
            FAIL_FAST="--fail-fast"
            shift
            ;;
        --help|-h)
            head -30 "$0" | tail -28
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

cd "$PROJECT_ROOT"

# Verify manifest exists
if [[ ! -f "$MANIFEST" ]]; then
    echo "Error: Test manifest not found at $MANIFEST"
    exit 1
fi

# Get test files for suite from manifest
get_suite_tests() {
    local suite="$1"
    python3 -c "
import json
import glob
from pathlib import Path

with open('$MANIFEST') as f:
    manifest = json.load(f)

suite_config = manifest.get('suites', {}).get('$suite')
if not suite_config:
    print('Suite not found: $suite', file=__import__('sys').stderr)
    exit(1)

tests = suite_config.get('tests', [])
for pattern in tests:
    if '*' in pattern:
        for f in glob.glob(f'tests/{pattern}'):
            print(f)
    else:
        test_path = f'tests/{pattern}'
        if Path(test_path).exists():
            print(test_path)
"
}

# Check if Mesen2 is running
check_mesen2() {
    local socket_path="${MESEN2_SOCKET_PATH:-}"

    if [[ -z "$socket_path" ]]; then
        # Auto-detect socket (only if exactly one exists)
        local nullglob_state
        shopt -q nullglob
        nullglob_state=$?
        shopt -s nullglob
        local sockets=(/tmp/mesen2-*.sock)
        if [[ $nullglob_state -ne 0 ]]; then
            shopt -u nullglob
        fi

        if [[ ${#sockets[@]} -eq 1 && -S "${sockets[0]}" ]]; then
            socket_path="${sockets[0]}"
            echo "Warning: auto-attaching to sole socket: ${socket_path}"
        elif [[ ${#sockets[@]} -gt 1 ]]; then
            echo "Error: multiple Mesen2 sockets found. Set MESEN2_SOCKET_PATH or close extra instances."
            for sock in "${sockets[@]}"; do
                echo "  - ${sock}"
            done
            return 1
        fi
    fi

    if [[ -z "$socket_path" || ! -S "$socket_path" ]]; then
        echo "Warning: Mesen2 socket not found. Tests may fail."
        echo "Start Mesen2 with: ./scripts/start_debug_session.sh"
        return 1
    fi

    export MESEN2_SOCKET_PATH="$socket_path"
    return 0
}

# Run a single test
run_test() {
    local test_file="$1"
    local test_args=""

    [[ -n "$VERBOSE" ]] && test_args="$test_args -v"
    [[ "$MOE_ENABLED" == "1" ]] && test_args="$test_args --moe-enabled"
    [[ "$OUTPUT_FORMAT" == "json" ]] && test_args="$test_args --output-format json"
    [[ "$OUTPUT_FORMAT" == "junit" ]] && test_args="$test_args --output-format junit"

    python3 scripts/test_runner.py "$test_file" $test_args
}

# Main execution
echo "========================================"
echo "Oracle of Secrets Regression Test Suite"
echo "========================================"
echo "Suite: $SUITE"
echo "MoE Analysis: $([ "$MOE_ENABLED" == "1" ] && echo "enabled" || echo "disabled")"
echo "Output: $OUTPUT_FORMAT"
echo ""

# Check Mesen2 connection
if ! check_mesen2; then
    echo ""
    read -p "Continue without Mesen2? (tests will likely fail) [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Get tests for suite
TESTS=$(get_suite_tests "$SUITE")
if [[ -z "$TESTS" ]]; then
    echo "No tests found for suite: $SUITE"
    exit 1
fi

# Count tests
TEST_COUNT=$(echo "$TESTS" | wc -l | tr -d ' ')
echo "Running $TEST_COUNT test(s)..."
echo ""

# Run tests
PASSED=0
FAILED=0
SKIPPED=0

while IFS= read -r test_file; do
    if [[ -z "$test_file" ]]; then
        continue
    fi

    test_name=$(basename "$test_file" .json)
    echo ">>> Running: $test_name"

    if run_test "$test_file"; then
        ((PASSED++))
        echo "    PASSED"
    else
        exit_code=$?
        if [[ $exit_code -eq 2 ]]; then
            ((SKIPPED++))
            echo "    SKIPPED"
        else
            ((FAILED++))
            echo "    FAILED"

            if [[ -n "$FAIL_FAST" ]]; then
                echo ""
                echo "Stopping due to --fail-fast"
                break
            fi
        fi
    fi
    echo ""
done <<< "$TESTS"

# Summary
echo "========================================"
echo "Results: $PASSED passed, $FAILED failed, $SKIPPED skipped"
echo "========================================"

# Exit with failure if any tests failed
if [[ $FAILED -gt 0 ]]; then
    exit 1
fi

exit 0
