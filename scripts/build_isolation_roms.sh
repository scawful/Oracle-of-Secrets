#!/bin/bash
set -euo pipefail

# Build isolation test ROMs — one per disabled module.
# Each ROM goes to Roms/isolation_test/oos168x_no-<module>.sfc
# Skips tests and static analysis for speed.

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

MODULES=(menu overworld patches sprites masks items dungeon music)
OUT_DIR="Roms/isolation_test"
mkdir -p "$OUT_DIR"

PASS=()
FAIL=()

for mod in "${MODULES[@]}"; do
  echo ""
  echo "========================================"
  echo "  Building with $mod DISABLED"
  echo "========================================"

  # Set flags
  python3 scripts/set_module_flags.py --profile all --disable "$mod"

  # Build (skip tests + analysis)
  set +e
  SKIP_TESTS=1 OOS_ANALYSIS_FATAL=0 ./scripts/build_rom.sh 168 --skip-tests --no-symbols 2>&1 | tail -5
  rc=$?
  set -e

  if [[ $rc -eq 0 && -f "Roms/oos168x.sfc" ]]; then
    cp "Roms/oos168x.sfc" "$OUT_DIR/oos168x_no-${mod}.sfc"
    echo "[+] SUCCESS: $OUT_DIR/oos168x_no-${mod}.sfc"
    PASS+=("$mod")
  else
    echo "[-] FAILED to build with $mod disabled (exit $rc)"
    FAIL+=("$mod")
  fi
done

# Restore all modules enabled
python3 scripts/set_module_flags.py --profile all
echo ""
echo "========================================"
echo "  Restored module_flags.asm to all-enabled"
echo "========================================"

echo ""
echo "======== RESULTS ========"
echo "Built OK: ${PASS[*]:-none}"
echo "Failed:   ${FAIL[*]:-none}"
echo ""
echo "Test each ROM in Mesen2 against save states 1 & 2."
echo "If a ROM does NOT crash, that disabled module is the culprit."
ls -la "$OUT_DIR/"
