#!/usr/bin/env python3
"""Idempotent base-ROM applier for Q-OOS-06 Consumable Islands (Option A).

Applies ONLY the two Option A overworld sprite edits via z3ed:
  1. Map $B0 (Goron Coast, phase 1): nudge Rock Meat sprite $52 from red-channel
     tile (21,11) onto tan-yard tile (16,12).
  2. Map $B6 (Sunlit Sandbar, phase 1): add Pineapple sprite $52 at (19,15).
     Explicitly uses phase 1 (spriteset $1B, sheets [BE, 9D, AB, CF]) because
     phase 0 ($00) and phase 2 ($04) fail the sprite-$52 sheet compatibility rule.

Refuses to touch the live .yazeproj ROM or shared Roms/oos168*.sfc unless
--allow-live-rom is passed explicitly (which requires scawful's direct approval).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

TRACK = "Q-OOS-06"
LIVE_ROM_MARKERS = (
    Path("/Users/scawful/Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj/rom"),
    ROOT / "Roms" / "oos168.sfc",
    ROOT / "Roms" / "oos168x.sfc",
)

# Exact Option A sprite operations (all phase 1, spriteset $1B -> $52 legal).
B0_SCREEN = 0xB0
B0_PHASE = 1
B0_SPRITE_ID = 0x52
B0_OLD_TILE = (21, 11)
B0_NEW_TILE = (16, 12)

B6_SCREEN = 0xB6
B6_PHASE = 1
B6_SPRITE_ID = 0x52
B6_TILE = (19, 15)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def is_protected_rom(rom: Path) -> bool:
    resolved = rom.resolve()
    for marker in LIVE_ROM_MARKERS:
        try:
            if resolved == marker.resolve():
                return True
        except OSError:
            if str(resolved) == str(marker):
                return True
    return False


def _extract_json(raw: str) -> dict[str, Any]:
    start = raw.find("{")
    if start < 0:
        raise RuntimeError(f"Expected JSON output from z3ed, got:\n{raw}")
    return json.loads(raw[start:])


def _run_z3ed(args: list[str]) -> str:
    proc = subprocess.run(
        ["z3ed", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"z3ed {' '.join(args)} failed (rc={proc.returncode}):\n"
            f"{proc.stdout}\n{proc.stderr}"
        )
    return proc.stdout


def list_sprites(rom: Path, screen: int, phase: int) -> list[dict[str, Any]]:
    raw = _run_z3ed(
        [
            "overworld-list-sprites",
            f"--rom={rom}",
            f"--screen=0x{screen:02X}",
            f"--phase={phase}",
            "--format=json",
        ]
    )
    doc = _extract_json(raw)
    return list(doc["Overworld Sprites"]["sprites"])


def _parse_tile(text: str) -> tuple[int, int]:
    m = re.match(r"^\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*$", text)
    if not m:
        raise ValueError(f"Unexpected tile string {text!r}")
    return int(m.group(1)), int(m.group(2))


def plan_edits(
    b0_sprites: list[dict[str, Any]],
    b6_sprites: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compute idempotent Option A edits from listed phase-1 sprites."""
    ops: list[dict[str, Any]] = []

    # 1. Map $B0 Rock Meat nudge (21,11) -> (16,12)
    b0_at_new = [
        s
        for s in b0_sprites
        if int(s["sprite_id"], 16) == B0_SPRITE_ID and _parse_tile(s["tile"]) == B0_NEW_TILE
    ]
    b0_at_old = [
        s
        for s in b0_sprites
        if int(s["sprite_id"], 16) == B0_SPRITE_ID and _parse_tile(s["tile"]) == B0_OLD_TILE
    ]
    if b0_at_new and not b0_at_old:
        ops.append(
            {
                "id": "rock_meat_b0_interior",
                "action": "already_applied",
                "screen": f"0x{B0_SCREEN:02X}",
                "phase": B0_PHASE,
                "sprite_id": f"0x{B0_SPRITE_ID:02X}",
                "list_index": b0_at_new[0]["list_index"],
                "from_tile": list(B0_OLD_TILE),
                "to_tile": list(B0_NEW_TILE),
            }
        )
    elif len(b0_at_old) == 1 and not b0_at_new:
        ops.append(
            {
                "id": "rock_meat_b0_interior",
                "action": "move_sprite",
                "screen": f"0x{B0_SCREEN:02X}",
                "phase": B0_PHASE,
                "sprite_id": f"0x{B0_SPRITE_ID:02X}",
                "list_index": int(b0_at_old[0]["list_index"]),
                "from_tile": list(B0_OLD_TILE),
                "to_tile": list(B0_NEW_TILE),
            }
        )
    else:
        raise RuntimeError(
            f"Unexpected $B0 phase-{B0_PHASE} $52 state: "
            f"at_old={len(b0_at_old)}, at_new={len(b0_at_new)}, sprites={b0_sprites}"
        )

    # 2. Map $B6 Pineapple add at (19,15) in phase 1
    b6_at_pin = [
        s
        for s in b6_sprites
        if int(s["sprite_id"], 16) == B6_SPRITE_ID and _parse_tile(s["tile"]) == B6_TILE
    ]
    if b6_at_pin:
        ops.append(
            {
                "id": "pineapple_sandbar",
                "action": "already_applied",
                "screen": f"0x{B6_SCREEN:02X}",
                "phase": B6_PHASE,
                "sprite_id": f"0x{B6_SPRITE_ID:02X}",
                "tile": list(B6_TILE),
            }
        )
    else:
        ops.append(
            {
                "id": "pineapple_sandbar",
                "action": "add_sprite",
                "screen": f"0x{B6_SCREEN:02X}",
                "phase": B6_PHASE,
                "sprite_id": f"0x{B6_SPRITE_ID:02X}",
                "tile": list(B6_TILE),
            }
        )

    return ops


def execute_ops(rom: Path, ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for op in ops:
        act = op["action"]
        if act == "already_applied":
            results.append({**op, "status": "unchanged"})
        elif act == "move_sprite":
            tx, ty = op["to_tile"]
            _run_z3ed(
                [
                    "overworld-move-sprite",
                    f"--rom={rom}",
                    f"--screen={op['screen']}",
                    f"--phase={op['phase']}",
                    f"--index={op['list_index']}",
                    f"--x={tx}",
                    f"--y={ty}",
                    f"--expect-id={op['sprite_id']}",
                    "--write",
                ]
            )
            results.append({**op, "status": "applied"})
        elif act == "add_sprite":
            tx, ty = op["tile"]
            _run_z3ed(
                [
                    "overworld-add-sprite",
                    f"--rom={rom}",
                    f"--screen={op['screen']}",
                    f"--phase={op['phase']}",
                    f"--id={op['sprite_id']}",
                    f"--x={tx}",
                    f"--y={ty}",
                    "--write",
                ]
            )
            results.append({**op, "status": "applied"})
        else:
            raise ValueError(f"Unknown action {act!r}")
    return results


def verify_rom(rom: Path, out_dir: Path | None = None) -> dict[str, Any]:
    """Run z3ed overworld-validate, strict sheet compat, and planner audit."""
    report: dict[str, Any] = {}

    val_raw = _run_z3ed(
        ["overworld-validate", f"--rom={rom}", "--include-tail", "--format=json"]
    )
    val_doc = _extract_json(val_raw)
    report["overworld_validate"] = val_doc

    # Verify strict sprite-sheet compatibility across the entire ROM
    sheet_proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "Scripts" / "Build" / "check_sprite_sheet_compat.py"),
            "--strict",
            "--rom",
            str(rom),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    report["sprite_sheet_compat_rc"] = sheet_proc.returncode
    report["sprite_sheet_compat_out"] = (sheet_proc.stdout + sheet_proc.stderr).strip()
    if sheet_proc.returncode != 0:
        raise RuntimeError(
            f"check_sprite_sheet_compat.py --strict failed:\n{report['sprite_sheet_compat_out']}"
        )

    # Confirm post-apply idempotency
    post_ops = plan_edits(
        list_sprites(rom, B0_SCREEN, B0_PHASE),
        list_sprites(rom, B6_SCREEN, B6_PHASE),
    )
    not_done = [op for op in post_ops if op["action"] != "already_applied"]
    if not_done:
        raise RuntimeError(f"Post-apply state not idempotent: {not_done}")
    report["post_apply_ops"] = post_ops

    # Run plan_consumable_islands.py against the patched ROM and verify every
    # placement passes (with the two newly placed $52 sprites allowed to occupy
    # their exact target tile in phase 1).
    plan_dir = out_dir / "post_plan" if out_dir else rom.parent / "post_plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "Scripts" / "Proposals" / "plan_consumable_islands.py"),
            "--rom",
            str(rom),
            "--out-dir",
            str(plan_dir),
            "--no-render",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    manifest_path = plan_dir / "consumable_islands_manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(
            f"plan_consumable_islands.py produced no manifest:\n{plan_proc.stdout}\n{plan_proc.stderr}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    applied_ids = {"rock_meat_b0_interior", "pineapple_sandbar"}
    unexpected: list[str] = []
    for row in manifest["placements"]:
        rid = row["id"]
        if rid in applied_ids:
            probs = [p for p in row.get("problems", []) if p != "tile already has a sprite"]
            on_tile = row.get("sprites_on_tile", [])
            has_52_p1 = any(
                str(s.get("id", "")).lower() == "0x52" and s.get("phase") == 1
                for s in on_tile
            )
            if probs or not has_52_p1:
                unexpected.append(f"{rid}: problems={probs}, sprites_on_tile={on_tile}")
        elif row.get("status") != "pass":
            unexpected.append(f"{rid}: status={row.get('status')}, problems={row.get('problems')}")
    if unexpected:
        raise RuntimeError(f"Post-apply manifest audit failed: {unexpected}")
    report["planner_manifest_ok"] = True
    report["planner_applied_verified"] = sorted(applied_ids)
    report["planner_other_passed"] = len(manifest["placements"]) - len(applied_ids)

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Idempotent Option A sprite applier for Q-OOS-06 Consumable Islands."
    )
    parser.add_argument("--rom", required=True, type=Path, help="Target ROM path (private copy by default)")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the planned Option A edits to --rom (default is dry-run plan only)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run overworld-validate, strict sprite-sheet compat, and planner checks",
    )
    parser.add_argument(
        "--allow-live-rom",
        action="store_true",
        help="Override refusal of live .yazeproj/rom or shared Roms/oos168*.sfc",
    )
    parser.add_argument("--out-json", type=Path, help="Optional JSON receipt output path")
    args = parser.parse_args(argv)

    rom = args.rom
    if not rom.is_file():
        print(f"ERROR: ROM not found: {rom}", file=sys.stderr)
        return 2

    if is_protected_rom(rom) and not args.allow_live_rom:
        print(
            f"REFUSED: {rom} is a protected live/shared ROM. "
            "Operate on a private copy, or pass --allow-live-rom only after explicit user OK.",
            file=sys.stderr,
        )
        return 3

    before_sha = sha256_file(rom)
    ops = plan_edits(
        list_sprites(rom, B0_SCREEN, B0_PHASE),
        list_sprites(rom, B6_SCREEN, B6_PHASE),
    )

    receipt: dict[str, Any] = {
        "track": TRACK,
        "rom": str(rom),
        "mode": "apply" if args.apply else "plan",
        "sha256_before": before_sha,
        "planned_ops": ops,
    }

    if args.apply:
        receipt["results"] = execute_ops(rom, ops)
        receipt["sha256_after"] = sha256_file(rom)
    else:
        receipt["sha256_after"] = before_sha

    if args.verify:
        receipt["verification"] = verify_rom(rom, args.out_json.parent if args.out_json else None)

    summary = json.dumps(receipt, indent=2)
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(summary + "\n", encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
