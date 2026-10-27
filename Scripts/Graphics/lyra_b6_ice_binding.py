#!/usr/bin/env python3
"""Bind the B6 native16 ICE kit to catalog data without opening or writing a ROM.

Input is Lyra's native16 kit (3bpp page 1, logical Tile16 words, 8-word palette)
and the bound placement recipe for parent 182. The ICE page is raised to
native-high 4bpp (index n -> n|8, 0 stays transparent), quadrants are deduped
under h/v flip, and the result is either a demand plan (no allocation) or, with
an explicit allocation, a catalog/policy fragment, Tile16 records, global tile
type bytes and a palette row plan. The fragment is validated against the live
catalog and runtime policy in memory; neither file is written here.

Collision follows scawful 2026-10-27: slippery ice, tile type $0E for every ICE
character. OverworldTileTypes ($0E9459) is global and indexed by character, so
an allocated character's type applies on every map that draws it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compile_graphics_pack as pack
import compile_runtime_graphics as runtime

ROOT = Path(__file__).resolve().parents[2]
PARENT_MAP = 182
PROFILE_ID = "b6-snow-ice"
RESOURCE_PATH = "gfx/lyra_b6_ice.bin"
ICE_TYPE = 0x0E
TILE_TYPES_PC = 0x071459  # OverworldTileTypes, SNES $0E9459, 512 bytes
AUX_CHR = range(192, 448)  # VRAM words $2C00..$3BFF at BG base $2000
TILE16_CAPACITY = 4096
PINS = {
    "page-1.3bpp.bin": "5201dc9c16daa33cffcdff1d9d116485f8e7c8057930c06e0e996518ae582001",
    "tiles16.logical.bin": "67aa25ff25a3f05516aeb1aa92387677d7911969c7bb99c447d94ac984def543",
    "palette.bgr555.bin": "6b3d3e121f09ddbd5788b1e1e93f3cc68488f2235066a4c68abe10fb61bdb354",
    "recipe": "4165837cf75ea330a65f332aefee9307e4fb42295d835677244300b5957cdde5",
}
ICE_TILES = [f"I{n:02d}" for n in range(16)]  # logical tiles 16..31
FLIPS = ((False, False), (True, False), (False, True), (True, True))


def decode_3bpp(page: bytes, character: int) -> tuple:
    b = page[character * 24:character * 24 + 24]
    if len(b) != 24:
        raise pack.PackError(f"3bpp page has no character {character}")
    return tuple(tuple(((b[r * 2] >> (7 - x)) & 1) | (((b[r * 2 + 1] >> (7 - x)) & 1) << 1) |
                       (((b[16 + r] >> (7 - x)) & 1) << 2) for x in range(8)) for r in range(8))


def encode_4bpp_high(pixels: tuple) -> bytes:
    """Planes 0/1 then 2/3, row-interleaved; opaque 1..7 becomes 9..15."""
    out = bytearray(32)
    for r, row in enumerate(pixels):
        for x, index in enumerate(row):
            value = index | 8 if index else 0
            bit = 1 << (7 - x)
            for plane in range(4):
                if value >> plane & 1:
                    out[(plane // 2) * 16 + r * 2 + plane % 2] |= bit
    return bytes(out)


def flip(pixels: tuple, h: bool, v: bool) -> tuple:
    rows = pixels[::-1] if v else pixels
    return tuple(row[::-1] if h else row for row in rows)


def plan(page: bytes, tile16_words: bytes, roles: list[str]) -> dict:
    """Dedupe the used ICE quadrants. Kit words are page-1 chars $040+ (no flips)."""
    unknown = sorted(set(roles) - set(ICE_TILES))
    if unknown or not roles:
        raise pack.PackError(f"recipe uses non-ICE or no tiles: {unknown}")
    if len(tile16_words) != 32 * 8:
        raise pack.PackError("logical Tile16 table must hold 32 records")
    glyphs, quadrants = [], {}
    for role in sorted(set(roles)):
        logical = 16 + ICE_TILES.index(role)
        words = [int.from_bytes(tile16_words[logical * 8 + q * 2:logical * 8 + q * 2 + 2], "little")
                 for q in range(4)]
        entry = []
        for word in words:
            if word & 0xE000 or not 0x40 <= word & 0x3FF < 0x80:
                raise pack.PackError(f"{role} word {word:04X} is not an unflipped page-1 char")
            pixels = decode_3bpp(page, (word & 0x3FF) - 0x40)
            for h, v in FLIPS:
                candidate = flip(pixels, h, v)
                if candidate in glyphs:
                    entry.append(dict(glyph=glyphs.index(candidate), h=h, v=v))
                    break
            else:
                glyphs.append(pixels)
                entry.append(dict(glyph=len(glyphs) - 1, h=False, v=False))
        quadrants[role] = entry
    resource = b"".join(encode_4bpp_high(g) for g in glyphs)
    return dict(glyphs=glyphs, quadrants=quadrants, resource=resource,
                resource_id=f"snes4bpp:{pack.sha256(resource)}")


def _allocation(document: dict, glyph_count: int, roles: list[str]) -> dict:
    a = pack._fields(document, {"schema_version", "parent_map", "palette_row", "priority",
                                "chr", "tile16"}, "B6 allocation")
    if pack.integer(a["schema_version"], "allocation schema_version") != 1:
        raise pack.PackError("allocation schema_version must be 1")
    if a["parent_map"] != PARENT_MAP:
        raise pack.PackError(f"allocation must target parent {PARENT_MAP}")
    pack.integer(a["palette_row"], "palette_row", 7)
    if a["priority"] not in (0, 1):
        raise pack.PackError("priority must be 0 or 1")
    chars = pack.list_value(a["chr"], "chr", nonempty=True)
    if len(chars) != glyph_count or len(set(chars)) != len(chars):
        raise pack.PackError(f"allocation needs {glyph_count} unique characters")
    for c in chars:
        if pack.integer(c, "chr", 0x3FF) not in AUX_CHR:
            raise pack.PackError(f"chr {c} is outside auxiliary staging 192..447")
    tile16 = pack.object_value(a["tile16"], "tile16")
    if set(tile16) != set(roles):
        raise pack.PackError("tile16 must name exactly the recipe's ICE roles")
    ids = [pack.integer(tile16[r], f"tile16 {r}", TILE16_CAPACITY - 1) for r in roles]
    if len(set(ids)) != len(ids):
        raise pack.PackError("tile16 IDs must be unique")
    return a


def bind(result: dict, palette: bytes, allocation: dict) -> dict:
    roles = sorted(result["quadrants"])
    a = _allocation(allocation, len(result["glyphs"]), roles)
    chars = a["chr"]
    transfers = [dict(byte_count=32, resource_id=result["resource_id"], source_offset=i * 32,
                      vram_word_address=0x2000 + c * 16) for i, c in enumerate(chars)]
    transfers.sort(key=lambda t: t["vram_word_address"])
    catalog = dict(
        resources={result["resource_id"]: dict(byte_count=len(result["resource"]),
                                                format="snes4bpp", path=RESOURCE_PATH,
                                                sha256=pack.sha256(result["resource"]))},
        profiles={PROFILE_ID: dict(authoring_contract=dict(
            background_pixel_index=0, forbidden_opaque_indices=[8],
            kind="native-high-import", schema_version=1),
            bg_character_base_word=0x2000, transfers=transfers)},
        bindings=[dict(parent_maps=[PARENT_MAP], profile_id=PROFILE_ID)])
    slots = sorted({(c * 16) // 0x400 for c in chars})
    policy = {PROFILE_ID: dict(cache_slots=slots, late=None, normal="all_declared_transfers",
                               runtime_enabled=False, staging=dict(
                                   mode="native_after_conversion", vram_end_word=0x3C00,
                                   vram_start_word=0x2C00, wram_base=0x7F0000),
                               transition=dict(mode="native_staging"))}
    records = {}
    for role in roles:
        words = [(q["v"] << 15) | (q["h"] << 14) | (a["priority"] << 13) |
                 (a["palette_row"] << 10) | chars[q["glyph"]] for q in result["quadrants"][role]]
        records[role] = dict(tile16_id=a["tile16"][role], words_hex=[f"{w:04X}" for w in words],
                             bytes_hex=b"".join(w.to_bytes(2, "little") for w in words).hex())
    kit_words = [int.from_bytes(palette[i * 2:i * 2 + 2], "little") for i in range(8)]
    base = a["palette_row"] * 16
    palette_plan = dict(row=a["palette_row"], half="high",
                        cgram=[dict(index=base + 8 + n, bgr555=f"{kit_words[n]:04X}")
                               for n in range(1, 8)],
                        unused=[base + 8], note="column 8 is forbidden by native-high-import")
    return dict(catalog_fragment=catalog, policy_fragment=policy, tile16_records=records,
                tile_types=[dict(chr=c, type=f"{ICE_TYPE:02X}") for c in sorted(chars)],
                palette_plan=palette_plan)


def validate_merged(fragment: dict, result: dict, catalog_path: Path, policy_path: Path) -> dict:
    """Merge into the live catalog/policy in memory and run the shared validators."""
    catalog, assets = pack.load(catalog_path, parent_count=192)
    merged = json.loads(json.dumps(catalog))
    for key in ("resources", "profiles"):
        clash = set(merged[key]) & set(fragment["catalog_fragment"][key])
        if clash:
            raise pack.PackError(f"live catalog already has {key}: {sorted(clash)}")
        merged[key].update(fragment["catalog_fragment"][key])
    merged["bindings"] = merged["bindings"] + fragment["catalog_fragment"]["bindings"]
    assets = dict(assets, **{result["resource_id"]: result["resource"]})
    policy = pack.read_json(policy_path)
    policy["profiles"] = dict(policy["profiles"], **fragment["policy_fragment"])
    pack.validate(merged, assets, parent_count=192)
    runtime.validate_authoring_contracts(merged, assets)
    lowered = pack.lower_runtime_policy(merged, assets, policy, parent_count=192)
    return dict(lowered_profile=lowered["profiles"][PROFILE_ID],
                parent=lowered["parents"][str(PARENT_MAP)])


def tile_type_report(rom: bytes, chars: list[int]) -> list[dict]:
    """Base-ROM types only: ASM patches (Items/ice_rod.asm) are not applied here."""
    table = rom[TILE_TYPES_PC:TILE_TYPES_PC + 512]
    if len(table) != 512:
        raise pack.PackError("ROM is too small for OverworldTileTypes")
    return [dict(chr=c, base_type=f"{table[c]:02X}", wanted=f"{ICE_TYPE:02X}",
                 changes_other_maps=table[c] != ICE_TYPE) for c in sorted(chars)]


def _read_pinned(path: Path, name: str) -> bytes:
    data = path.read_bytes()
    if pack.sha256(data) != PINS[name]:
        raise pack.PackError(f"{path} does not match the reviewed kit pin")
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kit", type=Path, required=True, help="native16-kit-01/compiled-b6")
    parser.add_argument("--recipe", type=Path, required=True, help="BOUND_PLACEMENT_RECIPE.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allocation", type=Path)
    parser.add_argument("--rom", type=Path, help="read-only base ROM for the type report")
    parser.add_argument("--catalog", type=Path, default=ROOT / "Overworld/graphics_catalog.json")
    parser.add_argument("--policy", type=Path,
                        default=ROOT / "Overworld/graphics_runtime_policy.json")
    args = parser.parse_args(argv)
    try:
        page = _read_pinned(args.kit / "page-1.3bpp.bin", "page-1.3bpp.bin")
        words = _read_pinned(args.kit / "tiles16.logical.bin", "tiles16.logical.bin")
        palette = _read_pinned(args.kit / "palette.bgr555.bin", "palette.bgr555.bin")
        recipe = json.loads(_read_pinned(args.recipe, "recipe"))
        if recipe["target_map_id"] != PARENT_MAP:
            raise pack.PackError("recipe does not target parent 182")
        roles = [p["tile_role"] for p in recipe["placements"]]
        result = plan(page, words, roles)
        used = sorted(result["quadrants"])
        report = dict(schema_version=1, parent_map=PARENT_MAP, profile_id=PROFILE_ID,
                      pins=PINS, collision="slippery ice, type $0E (scawful 2026-10-27)",
                      resource=dict(path=RESOURCE_PATH, id=result["resource_id"],
                                    byte_count=len(result["resource"])),
                      quadrants=result["quadrants"],
                      demand=dict(chr=len(result["glyphs"]), tile16=len(used),
                                  tile16_bytes=8 * len(used), palette_words=7,
                                  tile_types=len(result["glyphs"])),
                      rom_or_catalog_written=False)
        if args.allocation:
            fragment = bind(result, palette, pack.read_json(args.allocation))
            fragment["validation"] = validate_merged(fragment, result, args.catalog, args.policy)
            if args.rom:
                fragment["tile_type_report"] = tile_type_report(
                    args.rom.read_bytes(), [t["chr"] for t in fragment["tile_types"]])
            report.update(status="BOUND_DATA_ONLY", **fragment)
        else:
            report["status"] = "PLAN_ONLY_ALLOCATION_REQUIRED"
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "lyra_b6_ice.bin").write_bytes(result["resource"])
        (args.output / "B6_ICE_BINDING.json").write_bytes(pack.json_bytes(report))
    except (pack.PackError, OSError, KeyError, ValueError) as error:
        print(f"lyra_b6_ice_binding: {error}", file=sys.stderr)
        return 1
    print(f"{report['status']}: {len(result['glyphs'])} glyphs, {len(used)} Tile16 -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
