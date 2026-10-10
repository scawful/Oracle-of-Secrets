#!/bin/bash
# Run module isolation in FixPlan Phase 1B order: disable one module, build, prompt to test.
#
# Usage:
#   Scripts/Validate/run_module_isolation.sh [--next N]       # Manual: one step, then prompt
#   Scripts/Validate/run_module_isolation.sh --auto [ARGS]    # Automated: build + bisect_softlock per module
#
# Manual: With no args runs full cycle (disables masks, builds, prompts; ...; then resets).
# With --next N: step N only (1=masks .. 8=overworld, 9=reset).
# Automated: --auto runs Scripts/Validate/run_module_isolation_auto.py with the remaining
# ARGS (e.g. --auto --dry-run); it needs a Mesen2 socket + save state 1.
#
# After each build: load save state 1 (overworld) and state 2 (dungeon) in Mesen2 and test.
# If crash disappears, the disabled module is implicated; then bisect inside that module.
#
# Order (safest first): Masks, Music, Menu, Items, Patches, Sprites, Dungeon, Overworld.
# Plans (moved out of the repo 2026-10-06): AFS scratchpad/archive/repo-slim-2026-10-06/repo/
# Docs/Debugging/Issues/archive/OverworldSoftlock_FixPlan.md (Phase 1B) and Module_Isolation_Plan.md.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# FixPlan Phase 1B order (safest first)
MODULES=(masks music menu items patches sprites dungeon overworld)

reset_all() {
    cd "$PROJECT_ROOT"
    python3 Scripts/Build/set_module_flags.py --profile all
    ./Scripts/Build/build_rom.sh 168
    echo ""
    echo "All modules re-enabled and ROM built."
}

run_step() {
    local idx="$1"
    local module="$2"
    cd "$PROJECT_ROOT"
    echo "=========================================="
    echo "Step $idx: Disable $module"
    echo "=========================================="
    python3 Scripts/Build/set_module_flags.py --disable "$module"
    ./Scripts/Build/build_rom.sh 168
    echo ""
    echo "  Load save state 1 (overworld) and state 2 (dungeon) in Mesen2 and test."
    echo "  If crash is GONE, guilty module = $module. Then bisect inside that module."
    echo "  To run next step: Scripts/Validate/run_module_isolation.sh --next $((idx + 1))"
    echo "  To reset all:     Scripts/Validate/run_module_isolation.sh --next 9"
    echo ""
}

NEXT=""
AUTO=""
AUTO_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --next)
            NEXT="$2"
            shift 2
            ;;
        --auto)
            AUTO=1
            shift
            AUTO_ARGS=("$@")
            break
            ;;
        --help|-h)
            sed -n '2,/^$/s/^# \{0,1\}//p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

cd "$PROJECT_ROOT"

if [[ -n "$AUTO" ]]; then
    exec python3 Scripts/Validate/run_module_isolation_auto.py "${AUTO_ARGS[@]}"
fi

if [[ -n "$NEXT" ]]; then
    # Run a single step
    if [[ "$NEXT" -eq 9 ]]; then
        reset_all
        exit 0
    fi
    if [[ "$NEXT" -ge 1 && "$NEXT" -le 8 ]]; then
        run_step "$NEXT" "${MODULES[$((NEXT - 1))]}"
        exit 0
    fi
    echo "Invalid --next: $NEXT (use 1-8 for module steps, 9 for reset)"
    exit 1
fi

# Full cycle: steps 1-8 then reset
for i in "${!MODULES[@]}"; do
    run_step "$((i + 1))" "${MODULES[$i]}"
    read -p "Press Enter to continue to next module (or Ctrl+C to stop)..."
done

echo "Running reset (re-enable all, build)..."
reset_all
