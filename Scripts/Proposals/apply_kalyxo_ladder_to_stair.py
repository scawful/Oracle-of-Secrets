#!/usr/bin/env python3
"""Reversible Kalyxo + Special OW ($B0) Ladder-to-Stair Proposal Patcher.

Replaces the 14 unnecessary short (<= 2 Tile16s tall) rung-ladder spots across
Kalyxo ($00-$3F) flagged by `STAIR-001` — plus optionally the high-visibility
3-tile rung ladder on Special OW Shrine of Power ($B0) — with verified
biome-compatible carved stair Tile16s and removes orphaned 0x333/0x335 wooden
ladder rail tops directly above replaced cliff openings.

All edits verify expected source Tile16s before writing (compare-and-swap),
never touch live `.yazeproj/rom` or `Roms/` targets, and support `--dry-run`,
`--revert`, and `--verify`.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence

ROOT = Path(__file__).resolve().parents[2]
for _rel in ("Scripts/Overworld", "Scripts/Build", "Scripts/Tools"):
    _p = str(ROOT / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_overworld_seams as cos  # noqa: E402
import check_ow_grammar as cog  # noqa: E402
import scene_intent_common as sic  # noqa: E402


@dataclass(frozen=True)
class TileEdit:
    map_id: int
    lx: int
    ly: int
    before_tid: int
    after_tid: int


@dataclass(frozen=True)
class StairSpot:
    spot_id: str
    map_id: int
    label: str
    biome_family: str
    x0: int
    y0: int
    before_grid: tuple[tuple[int, ...], ...]
    after_grid: tuple[tuple[int, ...], ...]
    extra_edits: tuple[TileEdit, ...] = ()

    @property
    def edits(self) -> tuple[TileEdit, ...]:
        items: list[TileEdit] = list(self.extra_edits)
        for dy, (brow, arow) in enumerate(zip(self.before_grid, self.after_grid)):
            for dx, (btid, atid) in enumerate(zip(brow, arow)):
                items.append(TileEdit(self.map_id, self.x0 + dx, self.y0 + dy, btid, atid))
        return tuple(items)


KALYXO_SPOTS: tuple[StairSpot, ...] = (
    StairSpot(
        spot_id="kalyxo_01_ranch_south",
        map_id=0x01,
        label="Ranch South Cliff",
        biome_family="kalyxo_0x3c_cobble_steps",
        x0=6,
        y0=28,
        before_grid=(
            (0x46D, 0x16F, 0x16F, 0x434),
            (0x184, 0x17E, 0x17E, 0x185),
        ),
        after_grid=(
            (0x7E1, 0x7E1, 0x7E1, 0x7E1),
            (0x7E1, 0x7E1, 0x7E1, 0x7E1),
        ),
        extra_edits=(
            TileEdit(0x01, 6, 27, 0x333, 0x034),
            TileEdit(0x01, 9, 27, 0x335, 0x034),
        ),
    ),
    StairSpot(
        spot_id="kalyxo_0A_mushroom_hotel",
        map_id=0x0A,
        label="Mushroom Hotel Cliff",
        biome_family="hotel_fairy_0x51_wood_steps",
        x0=20,
        y0=24,
        before_grid=(
            (0x46D, 0x16F, 0x16F, 0x434),
            (0x184, 0x17E, 0x17E, 0x185),
        ),
        after_grid=(
            (0x530, 0x530, 0x530, 0x530),
            (0x530, 0x530, 0x530, 0x530),
        ),
        extra_edits=(
            TileEdit(0x0A, 20, 23, 0x333, 0x034),
            TileEdit(0x0A, 23, 23, 0x335, 0x034),
        ),
    ),
    StairSpot(
        spot_id="kalyxo_0B_castle_rear",
        map_id=0x0B,
        label="Castle Rear Gardens",
        biome_family="castle_0x52_carved_stairs",
        x0=27,
        y0=8,
        before_grid=(
            (0x46D, 0x434),
            (0x184, 0x185),
        ),
        after_grid=(
            (0x4AE, 0x4ED),
            (0x4AE, 0x4ED),
        ),
        extra_edits=(
            TileEdit(0x0B, 27, 7, 0x333, 0x034),
            TileEdit(0x0B, 28, 7, 0x335, 0x034),
        ),
    ),
    StairSpot(
        spot_id="kalyxo_15_water_step",
        map_id=0x15,
        label="Fairy Grove West Water Step",
        biome_family="hotel_fairy_0x51_wood_steps",
        x0=2,
        y0=21,
        before_grid=(
            (0x46D, 0x434),
            (0x184, 0x185),
        ),
        after_grid=(
            (0x530, 0x530),
            (0x530, 0x530),
        ),
        extra_edits=(
            TileEdit(0x15, 2, 20, 0x333, 0x034),
            TileEdit(0x15, 3, 20, 0x335, 0x034),
        ),
    ),
    StairSpot(
        spot_id="kalyxo_15_fairy_cliff",
        map_id=0x15,
        label="Fairy Grove Center Cliff",
        biome_family="hotel_fairy_0x51_wood_steps",
        x0=15,
        y0=13,
        before_grid=(
            (0x46D, 0x434),
            (0x184, 0x185),
        ),
        after_grid=(
            (0x530, 0x530),
            (0x530, 0x530),
        ),
        extra_edits=(
            TileEdit(0x15, 15, 12, 0x333, 0x034),
            TileEdit(0x15, 16, 12, 0x335, 0x034),
        ),
    ),
    StairSpot(
        spot_id="kalyxo_19_woods_creek",
        map_id=0x19,
        label="Lost Woods Creek Bank",
        biome_family="kalyxo_0x3c_cobble_steps",
        x0=16,
        y0=23,
        before_grid=(
            (0x46D, 0x434),
            (0x184, 0x185),
        ),
        after_grid=(
            (0x7E1, 0x7E1),
            (0x7E1, 0x7E1),
        ),
        extra_edits=(
            TileEdit(0x19, 16, 22, 0x333, 0x034),
            TileEdit(0x19, 17, 22, 0x335, 0x034),
        ),
    ),
    StairSpot(
        spot_id="kalyxo_1E_zora_pool",
        map_id=0x1E,
        label="Zora Sanctuary West Basin",
        biome_family="zora_0x55_stone_steps",
        x0=4,
        y0=23,
        before_grid=(
            (0x184, 0x185),
            (0x184, 0x185),
        ),
        after_grid=(
            (0x2E4, 0x2E4),
            (0x2E4, 0x2E4),
        ),
    ),
    StairSpot(
        spot_id="kalyxo_1F_zora_south",
        map_id=0x1F,
        label="Zora Sanctuary South Pool",
        biome_family="zora_0x55_stone_steps",
        x0=8,
        y0=29,
        before_grid=(
            (0x184, 0x185),
            (0x184, 0x185),
        ),
        after_grid=(
            (0x2E4, 0x2E4),
            (0x2E4, 0x2E4),
        ),
    ),
    StairSpot(
        spot_id="kalyxo_24_west_deck",
        map_id=0x24,
        label="Wayward West Wood Deck Step",
        biome_family="village_0x2f_stone_stairs",
        x0=10,
        y0=16,
        before_grid=(
            (0xAD4,),
            (0x3F6,),
        ),
        after_grid=(
            (0x3F1,),
            (0x3F1,),
        ),
    ),
    StairSpot(
        spot_id="kalyxo_24_canal_cliff",
        map_id=0x24,
        label="Wayward Canal Bank",
        biome_family="village_0x2f_stone_stairs",
        x0=14,
        y0=20,
        before_grid=(
            (0x46D, 0x434),
            (0x184, 0x185),
        ),
        after_grid=(
            (0x3F0, 0x3F2),
            (0x3F0, 0x3F2),
        ),
        extra_edits=(
            TileEdit(0x24, 14, 19, 0x333, 0x034),
            TileEdit(0x24, 15, 19, 0x335, 0x034),
        ),
    ),
    StairSpot(
        spot_id="kalyxo_25_pond_cliff",
        map_id=0x25,
        label="Field Pond Cliff",
        biome_family="village_0x2f_stone_stairs",
        x0=21,
        y0=24,
        before_grid=(
            (0x46D, 0x434),
            (0x184, 0x185),
        ),
        after_grid=(
            (0x3F0, 0x3F2),
            (0x3F0, 0x3F2),
        ),
        extra_edits=(
            TileEdit(0x25, 21, 23, 0x333, 0x034),
            TileEdit(0x25, 22, 23, 0x335, 0x034),
        ),
    ),
    StairSpot(
        spot_id="kalyxo_26_zora_dock",
        map_id=0x26,
        label="Zora East Dock Step",
        biome_family="zora_0x55_stone_steps",
        x0=19,
        y0=17,
        before_grid=(
            (0x46D, 0x174),
            (0x184, 0x185),
        ),
        after_grid=(
            (0x2E4, 0x2E4),
            (0x2E4, 0x2E4),
        ),
        extra_edits=(
            TileEdit(0x26, 19, 16, 0x333, 0x034),
            TileEdit(0x26, 20, 16, 0x335, 0x034),
        ),
    ),
    StairSpot(
        spot_id="kalyxo_2C_terrace_deck",
        map_id=0x2C,
        label="Loom Terrace Deck Step",
        biome_family="village_0x2f_stone_stairs",
        x0=18,
        y0=24,
        before_grid=(
            (0xAC8, 0xAC9),
            (0x184, 0x185),
        ),
        after_grid=(
            (0x3F0, 0x3F2),
            (0x3F0, 0x3F2),
        ),
    ),
    StairSpot(
        spot_id="kalyxo_3B_loom_mesa",
        map_id=0x3B,
        label="Loom Mesa North Approach",
        biome_family="kalyxo_0x3c_cobble_steps",
        x0=27,
        y0=0,
        before_grid=(
            (0x46D, 0x434),
            (0x184, 0x185),
        ),
        after_grid=(
            (0x7E1, 0x7E1),
            (0x7E1, 0x7E1),
        ),
        extra_edits=(
            TileEdit(0x33, 27, 31, 0x333, 0x034),
            TileEdit(0x33, 28, 31, 0x335, 0x034),
        ),
    ),
)

SPECIAL_SPOTS: tuple[StairSpot, ...] = (
    StairSpot(
        spot_id="special_B0_shrine_power",
        map_id=0xB0,
        label="Shrine of Power Approach",
        biome_family="special_0x3c_shrine_cobble_steps",
        x0=20,
        y0=22,
        before_grid=(
            (0x184, 0x17E, 0x17E, 0x185),
            (0x184, 0x17E, 0x17E, 0x185),
            (0x184, 0x17E, 0x17E, 0x185),
        ),
        after_grid=(
            (0x7E1, 0x7E1, 0x7E1, 0x7E1),
            (0x7E1, 0x7E1, 0x7E1, 0x7E1),
            (0x7E1, 0x7E1, 0x7E1, 0x7E1),
        ),
    ),
)


def _assert_safe_out_path(out_path: Path) -> None:
    resolved = str(out_path.resolve())
    lowered = resolved.lower()
    if ".yazeproj" in lowered or "/roms/" in lowered or resolved.endswith("/Roms"):
        raise ValueError(
            f"Refusing to write to live project or shared Roms/ path: {out_path}"
        )


def _set_tile_z3ed(
    z3ed_bin: Path,
    rom_path: Path,
    ctx: cog.GrammarContext,
    map_id: int,
    lx: int,
    ly: int,
    tid: int,
) -> None:
    par, _ = ctx.parent_and_size(map_id)
    ax = lx + (32 if (map_id - par) % 8 == 1 else 0)
    ay = ly + (32 if (map_id - par) // 8 == 1 else 0)
    proc = subprocess.run(
        [
            str(z3ed_bin),
            "overworld-set-tile",
            f"--rom={rom_path}",
            f"--map=0x{par:02X}",
            f"--x={ax}",
            f"--y={ay}",
            f"--tile=0x{tid:04X}",
            "--write",
            "--allow-lyra-layout-writes",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"z3ed overworld-set-tile failed on 0x{map_id:02X} ({lx},{ly}) "
            f"[parent 0x{par:02X} ({ax},{ay})]: {proc.stderr or proc.stdout}"
        )


def apply_spots(
    *,
    in_rom: Path,
    out_rom: Path,
    spots: Sequence[StairSpot],
    mode: str = "apply",
    dry_run: bool = False,
    manifest_path: Path | None = None,
) -> dict:
    if not dry_run:
        _assert_safe_out_path(out_rom)

    rom_bytes = sic.load_rom_bytes(in_rom)
    ctx = cog.GrammarContext(rom_bytes, root=ROOT)

    edits: list[TileEdit] = []
    for sp in spots:
        for ed in sp.edits:
            expected = ed.before_tid if mode == "apply" else ed.after_tid
            target = ed.after_tid if mode == "apply" else ed.before_tid
            actual = ctx.screen_grid(ed.map_id)[ed.ly][ed.lx]
            if actual != expected:
                raise ValueError(
                    f"Pre-check mismatch in {sp.spot_id} map 0x{ed.map_id:02X} "
                    f"({ed.lx},{ed.ly}): expected 0x{expected:03X}, found 0x{actual:03X}"
                )
            # Validate target Tile16 in apply mode is walkable/stair (0x22 or 0x48 grass for rail cleanup)
            if mode == "apply":
                tts = ctx.tile16_quadrant_types(ed.map_id, target)
                if target != 0x034 and 0x22 not in tts:
                    raise ValueError(
                        f"Replacement tile 0x{target:03X} on 0x{ed.map_id:02X} lacks TileType 0x22: {tts}"
                    )
            edits.append(TileEdit(ed.map_id, ed.lx, ed.ly, actual, target))

    summary = {
        "mode": mode,
        "dry_run": dry_run,
        "in_rom": str(in_rom),
        "out_rom": str(out_rom),
        "in_sha256": cog.sha256_bytes(rom_bytes),
        "spot_count": len(spots),
        "tile_edits": len(edits),
        "spots": [sp.spot_id for sp in spots],
    }

    if dry_run:
        return summary

    z3ed_bin = sic.find_z3ed_bin()
    if z3ed_bin is None or not z3ed_bin.is_file():
        raise RuntimeError("z3ed binary not found via scene_intent_common.find_z3ed_bin()")

    out_rom.parent.mkdir(parents=True, exist_ok=True)
    if out_rom.resolve() != in_rom.resolve():
        shutil.copyfile(in_rom, out_rom)

    for ed in edits:
        _set_tile_z3ed(z3ed_bin, out_rom, ctx, ed.map_id, ed.lx, ed.ly, ed.after_tid)

    # Read back all patched cells to assert exact round-trip persistence
    post_bytes = sic.load_rom_bytes(out_rom)
    post_ctx = cog.GrammarContext(post_bytes, root=ROOT)
    for ed in edits:
        got = post_ctx.screen_grid(ed.map_id)[ed.ly][ed.lx]
        if got != ed.after_tid:
            raise AssertionError(
                f"Post-write verification failed on 0x{ed.map_id:02X} ({ed.lx},{ed.ly}): "
                f"expected 0x{ed.after_tid:03X}, got 0x{got:03X}"
            )

    summary["out_sha256"] = cog.sha256_bytes(post_bytes)
    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_payload = {
            **summary,
            "edits": [
                {
                    "map_id": f"0x{e.map_id:02X}",
                    "x": e.lx,
                    "y": e.ly,
                    "from": f"0x{e.before_tid:03X}",
                    "to": f"0x{e.after_tid:03X}",
                }
                for e in edits
            ],
        }
        manifest_path.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")

    return summary


def verify_roms(in_rom: Path, out_rom: Path) -> dict:
    z3ed_bin = sic.find_z3ed_bin()
    if z3ed_bin is None:
        raise RuntimeError("z3ed binary not found")

    val = subprocess.run(
        [
            str(z3ed_bin),
            "overworld-validate",
            f"--rom={out_rom}",
            "--include-tail",
            "--check-tile16",
        ],
        capture_output=True,
        text=True,
    )
    if val.returncode != 0:
        raise RuntimeError(f"z3ed overworld-validate failed:\n{val.stdout}\n{val.stderr}")

    pre_seams = cos.audit_overworld_seams(sic.load_rom_bytes(in_rom), root=ROOT)
    post_seams = cos.audit_overworld_seams(sic.load_rom_bytes(out_rom), root=ROOT)

    def seam_tile_sigs(rep: dict) -> set[tuple]:
        out = set()
        for pair in rep["seam_errors"]:
            for idx in pair["error_tiles"]:
                out.add((pair["map_a"], pair["map_b"], pair["axis"], idx))
        return out

    new_seam_tiles = seam_tile_sigs(post_seams) - seam_tile_sigs(pre_seams)
    new_exit_errs = max(0, post_seams["exit_error_count"] - pre_seams["exit_error_count"])
    new_ent_errs = max(0, post_seams["entrance_error_count"] - pre_seams["entrance_error_count"])

    pre_gram = cog.audit_overworld_grammar(sic.load_rom_bytes(in_rom), root=ROOT)
    post_gram = cog.audit_overworld_grammar(sic.load_rom_bytes(out_rom), root=ROOT)

    return {
        "z3ed_validate_rc": val.returncode,
        "z3ed_validate_tail": val.stdout.strip().splitlines()[-10:],
        "seams_before_error_pairs": pre_seams["seam_error_pair_count"],
        "seams_after_error_pairs": post_seams["seam_error_pair_count"],
        "seams_before_error_tiles": pre_seams["total_seam_error_tiles"],
        "seams_after_error_tiles": post_seams["total_seam_error_tiles"],
        "seams_new_regressions": len(new_seam_tiles) + new_exit_errs + new_ent_errs,
        "grammar_total_before": pre_gram["total_findings"],
        "grammar_total_after": post_gram["total_findings"],
        "stair_001_before": pre_gram["counts_by_rule"].get("STAIR-001", 0),
        "stair_001_after": post_gram["counts_by_rule"].get("STAIR-001", 0),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in-rom", required=True, type=Path, help="Input ROM (read-only)")
    ap.add_argument("--out-rom", required=True, type=Path, help="Private output ROM copy")
    ap.add_argument(
        "--mode",
        choices=("apply", "revert"),
        default="apply",
        help="apply stair replacements or revert back to rung ladders",
    )
    ap.add_argument("--kalyxo-only", action="store_true", help="Skip Special OW $B0 spot")
    ap.add_argument("--dry-run", action="store_true", help="Check pre-conditions only without writing")
    ap.add_argument("--manifest", type=Path, help="Optional JSON manifest path")
    ap.add_argument("--verify", action="store_true", help="Run z3ed validate, seam audit, and grammar audit")
    args = ap.parse_args(argv)

    spots = list(KALYXO_SPOTS)
    if not args.kalyxo_only:
        spots.extend(SPECIAL_SPOTS)

    try:
        res = apply_spots(
            in_rom=args.in_rom,
            out_rom=args.out_rom,
            spots=spots,
            mode=args.mode,
            dry_run=args.dry_run,
            manifest_path=args.manifest,
        )
        if args.verify and not args.dry_run:
            res["verify"] = verify_roms(args.in_rom, args.out_rom)
    except (OSError, ValueError, RuntimeError, AssertionError) as exc:
        print(f"apply_kalyxo_ladder_to_stair: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(res, indent=2))
    if args.verify and not args.dry_run and res["verify"]["seams_new_regressions"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
