#!/usr/bin/env python3
"""Private-ROM Snowpeak sheet-$37 glyph fix plus Frost Glacier audit.

Copies a yaze ROM whose SHA-256 starts with 34e671c0 into /tmp and points
global sheet $37 at the corrected 2B/3B stream. Never touches the live project
ROM or Roms/oos168*.sfc. Map tiles are not restamped; the FSA/Minish kits stay
source assets with a Tile8 and collision-hint audit.

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
STREAM_POINTER = 0xB08000
MAPS = ("02", "03", "04", "05", "06", "07", "BE", "BF")


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


def fix_stream(rom: bytearray) -> dict:
    raw = sheet_codec.grid_to_sheet(sheet_codec.text_to_grid(SHEET37.read_text()))
    digest = hashlib.sha256(raw).hexdigest()
    if digest != "19279a4cee41b2ee83d52421256b8327dd50338b0a0c0994ee0ec08d35b515a8":
        raise SystemExit("snowpeak_sheet37.txt hash mismatch")
    before, before_len = sheet_table.decomp(rom, sheet_table.ptr(rom, 0x37))
    if len(before) != 1536:
        raise SystemExit(f"ROM sheet 37 decoded to {len(before)} bytes")
    old = sheet_codec.sheet_to_grid(before)
    new = sheet_codec.sheet_to_grid(raw)
    changed = []
    for tile in range(64):
        tx, ty = (tile % 16) * 8, (tile // 16) * 8
        if [old[ty + y][tx:tx + 8] for y in range(8)] != [new[ty + y][tx:tx + 8] for y in range(8)]:
            changed.append(tile)
    if changed != [0x2B, 0x3B]:
        raise SystemExit(f"sheet 37 diff is {changed}, expected tiles 2B and 3B")
    comp = lz2.compress(raw)
    if any(rom[STREAM_PC:STREAM_PC + len(comp)]):
        raise SystemExit(f"stream hole at {STREAM_PC:#x} is occupied")
    rom[STREAM_PC:STREAM_PC + len(comp)] = comp
    bank, high, low = (STREAM_POINTER >> 16) & 0xFF, (STREAM_POINTER >> 8) & 0xFF, STREAM_POINTER & 0xFF
    tables = ((sheet_table.TBL_BANK, bank), (sheet_table.TBL_HIGH, high), (sheet_table.TBL_LOW, low))
    if sheet_table.relocated(rom):
        tables += ((sheet_table.NEW_BANK, bank), (sheet_table.NEW_HIGH, high), (sheet_table.NEW_LOW, low))
    for table, value in tables:
        rom[sheet_table.pc(table) + 0x37] = value
    check, used = sheet_table.decomp(rom, sheet_table.ptr(rom, 0x37))
    if check != raw or used != len(comp):
        raise SystemExit("relocated sheet 37 did not round-trip")
    return {"previous_compressed": before_len, "compressed": len(comp), "pointer": f"0x{STREAM_POINTER:06X}",
            "pc": f"0x{STREAM_PC:06X}", "changed_tiles": ["0x2B", "0x3B"]}


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
    render(base, "05", proof / "map05-before.png")
    render(base, "BE", proof / "mapBE-before.png")
    before_sheet, _before_len = sheet_table.decomp(blob, sheet_table.ptr(blob, 0x37))
    rom = bytearray(blob)
    info = fix_stream(rom)
    after_sheet, _after_len = sheet_table.decomp(rom, sheet_table.ptr(rom, 0x37))
    write_glyph_proof(before_sheet, after_sheet, proof / "sheet37-glyphs.png")
    proposal.write_bytes(rom)
    refuse(proposal)
    doctor = json.loads(run(["z3ed", "rom-doctor", f"--rom={proposal}", "--format", "json"]).stdout)
    validate = run(["z3ed", "overworld-validate", f"--rom={proposal}", "--include-tail", "--check-tile16",
                    "--format", "json"]).stdout
    render(proposal, "05", proof / "map05-after.png")
    render(proposal, "BE", proof / "mapBE-after.png")
    described = {}
    for screen in MAPS:
        described[screen] = json.loads(run([
            "z3ed", "overworld-describe-map", f"--rom={proposal}", "--screen", screen, "--format", "json"
        ]).stdout)
    catalog = json.loads(run([
        "z3ed", "overworld-tile-catalog", f"--rom={proposal}", "--sheet", "37", "--format", "json"
    ]).stdout)
    reuse = run([
        "z3ed", "overworld-tile16-reuse-audit", f"--rom={proposal}", "--map", "05",
        "--find-for-map", "05", "--role", "cliff", "--limit", "5", "--format", "json"
    ]).stdout
    glacier = run([
        "z3ed", "overworld-tile16-reuse-audit", f"--rom={proposal}", "--map", "BE",
        "--find-for-map", "BE", "--role", "water-edge", "--limit", "5", "--format", "json"
    ]).stdout
    report = {
        "source_sha256": digest,
        "proposal": str(proposal),
        "proposal_sha256": hashlib.sha256(proposal.read_bytes()).hexdigest(),
        "sheet37": info,
        "checksum_valid": doctor.get("checksum_valid"),
        "map05_pixel_diff": png_diff(proof / "map05-before.png", proof / "map05-after.png"),
        "mapBE_pixel_diff": png_diff(proof / "mapBE-before.png", proof / "mapBE-after.png"),
        "static_graphics": {screen: described[screen]["static_graphics"] for screen in MAPS},
        "sheet37_catalog_screens": catalog["Overworld Tile Abstraction Catalog"]["loaded_sheets"][0]["screen_count"],
        "validate_bytes": len(validate),
        "cliff_audit_bytes": len(reuse),
        "glacier_audit_bytes": len(glacier),
    }
    (proof / "proposal_report.json").write_text(json.dumps(report, indent=2) + "\n")
    (proof / "map05-cliff-reuse.json").write_text(reuse)
    (proof / "mapBE-water-reuse.json").write_text(glacier)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
