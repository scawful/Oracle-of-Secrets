#!/usr/bin/env python3
"""Automated module isolation testing: disable one module, build, run softlock test, record result.

Runs the FixPlan Phase 1B order (Masks → Music → Menu → Items → Patches → Sprites → Dungeon →
Overworld). For each module: set disable flag, build ROM, optionally reload ROM in Mesen2, run
bisect_softlock test (load state 1, run N frames, check mode/PC). Records pass/fail/skip and
writes a summary + optional JSON report.

Usage:
  python3 scripts/run_module_isolation_auto.py [--no-reload] [--json results.json] [--frames 600]
  python3 scripts/run_module_isolation_auto.py --module menu   # Single module only
  python3 scripts/run_module_isolation_auto.py --dry-run      # Print steps, no build/test

Requires: Mesen2 running with socket; save state 1 (overworld repro) present.
After each build, ROM is reloaded via mesen2_client.py rom-load unless --no-reload.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

# FixPlan Phase 1B order (safest first)
MODULES_ORDER = [
    "masks",
    "music",
    "menu",
    "items",
    "patches",
    "sprites",
    "dungeon",
    "overworld",
]


def run_cmd(cmd: list[str], cwd: Path, timeout: int = 120, capture: bool = True) -> tuple[int, str, str]:
    r = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )
    return r.returncode, r.stdout or "", r.stderr or ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated module isolation: disable one module, build, test, record."
    )
    parser.add_argument(
        "--module",
        choices=MODULES_ORDER,
        help="Run only this module (e.g. menu), then exit without reset.",
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Do not reload ROM in Mesen2 after each build (use if Mesen2 auto-reloads).",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=600,
        help="Frames to run per test (default 600).",
    )
    parser.add_argument(
        "--slot",
        type=int,
        default=1,
        help="Save state slot (default 1 = overworld repro).",
    )
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="Write results to JSON file (e.g. results/module_isolation_auto.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print steps only; do not build or test.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output.",
    )
    args = parser.parse_args()

    modules_to_run = [args.module] if args.module else MODULES_ORDER
    rom_path = REPO_ROOT / "Roms" / "oos168x.sfc"
    results: list[dict] = []
    guilty_candidates: list[str] = []

    print("Module isolation (automated)")
    print("Order:", ", ".join(modules_to_run))
    print("ROM:", rom_path)
    print("Test: load state slot", args.slot, ", run", args.frames, "frames, check mode/PC")
    print("")

    for i, module in enumerate(modules_to_run, start=1):
        step = {"module": module, "step": i, "result": "skip", "note": ""}
        print(f"[{i}/{len(modules_to_run)}] Disable: {module}")

        if args.dry_run:
            print("  (dry-run: would set flags, build, reload, test)")
            results.append(step)
            continue

        # 1. Set disable flag
        rc, _, err = run_cmd(
            [sys.executable, str(SCRIPT_DIR / "set_module_flags.py"), "--disable", module],
            cwd=REPO_ROOT,
        )
        if rc != 0:
            step["result"] = "error"
            step["note"] = f"set_module_flags failed: {err.strip()}"
            print("  ERROR:", step["note"])
            results.append(step)
            continue

        # 2. Build
        rc, _, err = run_cmd(
            ["./scripts/build_rom.sh", "168"],
            cwd=REPO_ROOT,
            capture=not args.verbose,
        )
        if rc != 0:
            step["result"] = "build_fail"
            step["note"] = err.strip() or "Build failed"
            print("  BUILD FAILED")
            results.append(step)
            continue

        # 3. Reload ROM in Mesen2 (so new build is used)
        if not args.no_reload and rom_path.exists():
            rc, _, _ = run_cmd(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "mesen2_client.py"),
                    "rom-load",
                    str(rom_path),
                ],
                cwd=REPO_ROOT,
                timeout=10,
            )
            if rc != 0 and args.verbose:
                print("  (rom-load failed; continuing anyway)")

        # 4. Run softlock test (no build)
        rc, _, err = run_cmd(
            [
                sys.executable,
                str(SCRIPT_DIR / "bisect_softlock.py"),
                "--no-build",
                "--slot",
                str(args.slot),
                "--frames",
                str(args.frames),
            ]
            + (["-v"] if args.verbose else []),
            cwd=REPO_ROOT,
            timeout=60,
        )
        if rc == 125:
            step["result"] = "skip"
            step["note"] = "Mesen2 not connected or load/run failed"
            print("  SKIP (Mesen2/state)")
            results.append(step)
            continue
        if rc == 0:
            step["result"] = "pass"
            step["note"] = "No softlock in test window"
            print("  PASS (no crash) <- guilty candidate?")
            guilty_candidates.append(module)
        else:
            step["result"] = "fail"
            step["note"] = "Softlock or corruption detected"
            print("  FAIL (crash)")
        results.append(step)

    # Reset to all enabled (unless single-module run)
    if not args.module and not args.dry_run:
        print("")
        print("Resetting: all modules enabled, build...")
        run_cmd(
            [sys.executable, str(SCRIPT_DIR / "set_module_flags.py"), "--profile", "all"],
            cwd=REPO_ROOT,
        )
        run_cmd(["./scripts/build_rom.sh", "168"], cwd=REPO_ROOT, capture=not args.verbose)

    # Summary
    print("")
    print("Summary:")
    for r in results:
        print(f"  {r['module']:<10} {r['result']:<12} {r.get('note', '')}")
    if guilty_candidates:
        print("")
        print("Guilty candidates (crash GONE when disabled):", ", ".join(guilty_candidates))
        print("  -> Bisect inside that module next (comment out incsrc in its all_*.asm).")

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "modules_order": MODULES_ORDER,
            "slot": args.slot,
            "frames": args.frames,
            "results": results,
            "guilty_candidates": guilty_candidates,
        }
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("")
        print("Wrote:", out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
