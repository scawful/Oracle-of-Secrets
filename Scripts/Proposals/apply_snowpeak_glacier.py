#!/usr/bin/env python3
"""Private-ROM Snowpeak deep-cliff and Frost Glacier stamps.

Copies a yaze ROM whose SHA-256 is 34e671c0... into /tmp. Points the vanilla
graphics table (the table z3ed overworld-render reads) at edited sheets:
sheet $37 keeps the lyra-stage1 $2B/$3B glyphs and paints the blank $2C void
into a deep cliff; sheet $35/$36 deepen map $02's cliff faces; sheet $63
cracks the $BE/$BF ice floor. Tile16 $7BB (maps $05-$07 only) is remapped so
those cells draw the $2B/$3B glyphs. Never touches the live project ROM or
Roms/oos168*.sfc.

ENABLE_EXPANDED_GRAPHICS_TABLE is not defined in this tree. The asm packer in
generate_hack_manifest.py includes Data/graphics/snowpeak_sheet.json only when
that define is 1 and ENABLE_SOURCE_SPRITE_SHEETS is 1. Defining the flag is
outside this track (Util/macros.asm and Config/feature_flags.asm). Until then
the usable sheet is this private ROM pointer, not a generated asm include.

Usage:
  python3 Scripts/Proposals/apply_snowpeak_glacier.py --source <rom> --work-dir /tmp/oos-gfx-snowpeak
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Scripts/Generate"))
import lz2  # noqa: E402
import sheet_codec  # noqa: E402
import sheet_table  # noqa: E402

EXPECTED_SHA = "34e671c0dcba7c8afdbb1268709b24b31d3120319feb54627520fe43c8b94b79"
SHEET37 = ROOT / "Data/graphics/snowpeak_sheet37.txt"
LIVE = (
    Path("/Users/scawful/Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj/rom"),
    ROOT / "Roms/oos168.sfc",
    ROOT / "Roms/oos168x.sfc",
)
# Doctor-reported free expansion on this 4MB image. SNES $B0:8000.
STREAM_PC = 0x180000
MAPS = ("02", "03", "04", "05", "06", "07", "BE", "BF")
PROOF_MAPS = ("02", "03", "04", "05", "06", "07", "BE", "BF")
# Sheet $37 local tiles. $2C is the blank fill behind maps $05-$07 (tile16 $8F3).
CLIFF_TILES = (0x0D, 0x2C)
# Sheet $63 floor quadrant of tile16 $F00, used only on $BE/$BF.
ICE_TILES = (0x0B,)
# Sheet $36 faces for tile16 $A2F (map $02 only).
MAP02_SHEET36 = (0x1A, 0x21, 0x28, 0x2A)


def refuse(path: Path) -> None:
    resolved = path.resolve()
    for live in LIVE:
        if live.exists() and resolved == live.resolve():
            raise SystemExit(f"refusing live ROM {resolved}")
    if resolved.name.startswith("oos168") and "Roms" in resolved.parts:
        raise SystemExit(f"refusing shared ROM {resolved}")


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        tail = (res.stdout + res.stderr)[-1500:]
        raise SystemExit(f"FAILED ({res.returncode}): {' '.join(cmd)}\n{tail}")
    return res


def load_grid(rom: bytes | bytearray, sheet: int) -> list[list[int]]:
    raw, _used = sheet_table.decomp(rom, sheet_table.ptr(rom, sheet))
    if len(raw) != 1536:
        raise SystemExit(f"sheet {sheet:#x} decoded to {len(raw)} bytes")
    return sheet_codec.sheet_to_grid(raw)


def paint_tile(grid: list[list[int]], tile: int, rows: tuple[str, ...]) -> None:
    if len(rows) != 8 or any(len(row) != 8 for row in rows):
        raise SystemExit(f"tile {tile:#x} pattern is not 8x8")
    tx, ty = (tile % 16) * 8, (tile // 16) * 8
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            grid[ty + y][tx + x] = 0 if ch == "." else int(ch, 16)


DEEP_CLIFF = (
    "00000000",
    "77777777",
    "00000000",
    "00000000",
    "66666666",
    "00000000",
    "00000000",
    "77777777",
)
ICE_CRACKS = (
    (
        "55555555",
        "55555555",
        "55555555",
        "11111111",
        "55555555",
        "55555555",
        "55555555",
        "66666666",
    ),
)


def snes_pointer(pc: int) -> tuple[int, int, int]:
    bank = 0x80 | (pc // 0x8000)
    addr = 0x8000 | (pc & 0x7FFF)
    return bank, (addr >> 8) & 0xFF, addr & 0xFF


def install_sheet(rom: bytearray, sheet: int, grid: list[list[int]], cursor: int) -> tuple[int, dict]:
    raw = sheet_codec.grid_to_sheet(grid)
    comp = lz2.compress(raw)
    back, used = lz2.decompress(comp, 0)
    if back != raw or used != len(comp):
        raise SystemExit(f"sheet {sheet:#x} compressor did not round-trip")
    if cursor + len(comp) > 0x1E0000:
        raise SystemExit("sheet streams ran out of the free expansion")
    if any(rom[cursor:cursor + len(comp)]):
        raise SystemExit(f"stream hole at {cursor:#x} is occupied")
    rom[cursor:cursor + len(comp)] = comp
    bank, high, low = snes_pointer(cursor)
    rom[sheet_table.pc(sheet_table.TBL_BANK) + sheet] = bank
    rom[sheet_table.pc(sheet_table.TBL_HIGH) + sheet] = high
    rom[sheet_table.pc(sheet_table.TBL_LOW) + sheet] = low
    got, _got_len = sheet_table.decomp(rom, sheet_table.ptr(rom, sheet))
    if got != raw:
        raise SystemExit(f"sheet {sheet:#x} pointer did not read back")
    info = {"sheet": f"0x{sheet:02X}", "pc": f"0x{cursor:06X}",
            "pointer": f"0x{bank:02X}{high:02X}{low:02X}", "compressed": len(comp)}
    return cursor + ((len(comp) + 15) & ~15), info


def build_sheets(rom: bytearray) -> dict:
    text = sheet_codec.text_to_grid(SHEET37.read_text())
    digest = hashlib.sha256(sheet_codec.grid_to_sheet(text)).hexdigest()
    if digest != "19279a4cee41b2ee83d52421256b8327dd50338b0a0c0994ee0ec08d35b515a8":
        raise SystemExit("snowpeak_sheet37.txt hash mismatch")
    original = load_grid(rom, 0x37)
    changed = []
    for tile in range(64):
        tx, ty = (tile % 16) * 8, (tile // 16) * 8
        if [original[ty + y][tx:tx + 8] for y in range(8)] != [text[ty + y][tx:tx + 8] for y in range(8)]:
            changed.append(tile)
    if changed != [0x2B, 0x3B]:
        raise SystemExit(f"sheet 37 diff is {changed}, expected tiles 2B and 3B")
    for tile in CLIFF_TILES:
        paint_tile(text, tile, DEEP_CLIFF)
    ice = load_grid(rom, 0x63)
    paint_tile(ice, ICE_TILES[0], ICE_CRACKS[0])
    faces = load_grid(rom, 0x36)
    for tile in MAP02_SHEET36:
        tx, ty = (tile % 16) * 8, (tile // 16) * 8
        for x in range(8):
            faces[ty][tx + x] = 1
            faces[ty + 4][tx + x] = 1
    cursor = STREAM_PC
    cursor, sheet37 = install_sheet(rom, 0x37, text, cursor)
    cursor, sheet63 = install_sheet(rom, 0x63, ice, cursor)
    _cursor, sheet36 = install_sheet(rom, 0x36, faces, cursor)
    return {"sheet37": sheet37, "sheet63": sheet63, "sheet36": sheet36,
            "glyph_tiles": ["0x2B", "0x3B"], "cliff_tiles": ["0x0D", "0x2C"],
            "ice_tiles": ["0x0B"]}


def remap_glyphs(proposal: Path) -> None:
    """Draw the real $2B/$3B glyphs on tile16 $7BB (maps $05, $06, $07 only)."""
    out = proposal.with_name("snowpeak-glacier-glyphs.sfc")
    run([
        "z3ed", "overworld-tile16-remap",
        f"--rom={proposal}", f"--out={out}",
        "--tiles=7BB-7BB",
        "--map=6:105=12B", "--map=6:108=13B",
        "--allow-lyra-layout-writes",
    ])
    out.replace(proposal)


def render(rom: Path, screen: str, dest: Path) -> None:
    run(["z3ed", "overworld-render", f"--rom={rom}", f"--screen={screen}", f"--out={dest}",
         "--area-overlay=on", "--graphics-preview=off", "--scale=1"])


def write_glyph_proof(before: bytes, after: bytes, dest: Path) -> None:
    from PIL import Image
    old = sheet_codec.sheet_to_grid(before)
    new = sheet_codec.sheet_to_grid(after)
    palette = [(8, 16, 28), (210, 236, 255), (120, 170, 200), (40, 70, 96),
               (240, 248, 255), (16, 28, 40), (70, 120, 150), (255, 255, 255)]
    scale = 8
    image = Image.new("RGB", (2 * (8 * scale + 8) + 8, 2 * (8 * scale + 16)), (12, 12, 16))
    for col, tile in enumerate((0x2B, 0x3B)):
        tx, ty = (tile % 16) * 8, (tile // 16) * 8
        for row, grid in enumerate((old, new)):
            for y in range(8):
                for x in range(8):
                    color = palette[grid[ty + y][tx + x]]
                    for sy in range(scale):
                        for sx in range(scale):
                            image.putpixel((8 + col * (8 * scale + 8) + x * scale + sx,
                                            16 + row * (8 * scale + 16) + y * scale + sy), color)
    image.save(dest)


def png_diff(a: Path, b: Path) -> int:
    from PIL import Image
    left, right = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if left.size != right.size:
        return -1
    return sum(p != q for p, q in zip(left.getdata(), right.getdata()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--work-dir", type=Path, default=Path("/tmp/oos-gfx-snowpeak"))
    args = ap.parse_args(argv)
    source = args.source.resolve()
    if not source.is_file():
        raise SystemExit(f"missing source ROM {source}")
    work = args.work_dir.resolve()
    if not (str(work).startswith("/tmp/") or str(work).startswith("/private/tmp/")):
        raise SystemExit(f"work dir must stay under /tmp ({work})")
    work.mkdir(parents=True, exist_ok=True)
    blob = source.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != EXPECTED_SHA:
        raise SystemExit(f"source sha {digest} is not {EXPECTED_SHA}")
    base = work / "base-34e671c0.sfc"
    proposal = work / "snowpeak-glacier-proposal.sfc"
    proof = work / "proof"
    proof.mkdir(exist_ok=True)
    if not base.exists() or hashlib.sha256(base.read_bytes()).hexdigest() != digest:
        shutil.copyfile(source, base)
    for screen in PROOF_MAPS:
        render(base, screen, proof / f"map{screen}-before.png")
    before_sheet, _before_len = sheet_table.decomp(blob, sheet_table.ptr(blob, 0x37))
    rom = bytearray(blob)
    info = build_sheets(rom)
    after_sheet, _after_len = sheet_table.decomp(rom, sheet_table.ptr(rom, 0x37))
    write_glyph_proof(before_sheet, after_sheet, proof / "sheet37-glyphs.png")
    proposal.write_bytes(rom)
    refuse(proposal)
    remap_glyphs(proposal)
    doctor = json.loads(run(["z3ed", "rom-doctor", f"--rom={proposal}", "--format", "json"]).stdout)
    validate = run(["z3ed", "overworld-validate", f"--rom={proposal}", "--include-tail", "--check-tile16",
                    "--format", "json"]).stdout
    diffs = {}
    for screen in PROOF_MAPS:
        render(proposal, screen, proof / f"map{screen}-after.png")
        diffs[screen] = png_diff(proof / f"map{screen}-before.png", proof / f"map{screen}-after.png")
    described = {}
    for screen in MAPS:
        described[screen] = json.loads(run([
            "z3ed", "overworld-describe-map", f"--rom={proposal}", "--screen", screen, "--format", "json"
        ]).stdout)
    catalog = json.loads(run([
        "z3ed", "overworld-tile-catalog", f"--rom={proposal}", "--sheet", "37", "--format", "json"
    ]).stdout)
    report = {
        "source_sha256": digest,
        "proposal": str(proposal),
        "proposal_sha256": hashlib.sha256(proposal.read_bytes()).hexdigest(),
        "sheets": info,
        "checksum_valid": doctor.get("checksum_valid"),
        "pixel_diffs": diffs,
        "expanded_graphics_table": (
            "ENABLE_EXPANDED_GRAPHICS_TABLE is undefined. snowpeak_sheet.json is packed "
            "only when that define is 1 and ENABLE_SOURCE_SPRITE_SHEETS is 1. "
            "Unblock: set the define in Util/macros.asm and Config/feature_flags.asm, "
            "then the existing generator writes Core/Generated/source_sprite_sheets/snowpeak."
        ),
        "static_graphics": {screen: described[screen]["static_graphics"] for screen in MAPS},
        "sheet37_catalog_screens": catalog["Overworld Tile Abstraction Catalog"]["loaded_sheets"][0]["screen_count"],
        "validate_bytes": len(validate),
    }
    (proof / "proposal_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("proposal_sha256", "checksum_valid", "pixel_diffs", "sheets")}, indent=2))
    weak = {screen: diffs[screen] for screen in ("02", "05", "BE") if diffs[screen] < 1000}
    if weak:
        print(f"stamp too small: {weak}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
