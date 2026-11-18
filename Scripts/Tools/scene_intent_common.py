#!/usr/bin/env python3
"""Shared read-only ROM, graphics, palette, Tile16, and z3ed helpers.

Used by scene_intent_preflight.py and donor_formation_audition.py so all ROM
decoding, perceptual palette remapping, read-only staging guards, and ledger
integrations share a single source of truth.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterable

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJ_ROM = Path.home() / "Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj/rom"
DEFAULT_VANILLA_ROM = Path.home() / "src/hobby/roms/Legend of Zelda, The - A Link to the Past (USA).sfc"
DEFAULT_AFS_ROOT = Path.home() / ".context/projects/oracle-of-secrets"

# ALTTP / ZSCustomOverworld ROM constants (grounded in yaze overworld.h / inc/zelda.h / game_data.h).
VANILLA_SHEET_COUNT = 223
EXTENDED_SHEET_COUNT = 255
VANILLA_TILE16_COUNT = 3752
EXPANDED_TILE16_COUNT = 4096

PC_AREA_GFX = 0x7C9C
PC_AREA_PAL = 0x7D1C
PC_GFX_GROUPS1 = 0x5D97
PC_GFX_GROUPS2 = 0x6073
PC_PAL_GROUP = 0x75504
PC_TILETYPE = 0x71459
PC_OW_MAIN_PAL = 0xDE6C8
PC_OW_AUX_PAL = 0xDE86C
PC_OW_ANIM_PAL = 0xDE604
PC_HUD_PAL = 0xDD660
PC_DUN_MAIN_PAL = 0xDD734
PC_PALETTESET_IDS = 0x75460
PC_DUN_PAL_PTR_TABLE = 0xDEC4B

PC_MAP16_VANILLA = 0x78000
PC_MAP16_EXPANDED = 0x1E8000
PC_MAP16_EXP_FLAG = 0x02FD28
PC_MAP32_EXP_FLAG = 0x01772E
PC_MAP32_VANILLA = (0x18000, 0x1B400, 0x20000, 0x23400)
PC_MAP32_EXPANDED = (0x18000, 0x020000, 0x1F0000, 0x1F8000)
PC_MAP32_PTR_HI = 0x1794D
PC_MAP32_PTR_LO = 0x17B2D
PC_TAIL_PTR_MARKER = 0x1423FF
PC_TAIL_PTR_HI = 0x142400
PC_TAIL_PTR_LO = 0x142640

PC_ZS_CUSTOM_BG_PAL = 0x140000
PC_ZS_CUSTOM_BG_EN = 0x140140
PC_ZS_MAIN_PAL_EN = 0x140141
PC_ZS_ANIM_GFX_EN = 0x140143
PC_ZS_OVERLAY_EN = 0x140144
PC_ZS_VERSION = 0x140145
PC_ZS_TILE_GFX_EN = 0x140148
PC_ZS_MAIN_PAL_ARR = 0x140160
PC_ZS_ANIM_GFX_ARR = 0x1402A0
PC_ZS_OVERLAY_ARR = 0x140340
PC_ZS_TILE_GFX_ARR = 0x140480
PC_ZS_PARENT_EXPANDED = 0x140998

PC_ROOM_HEADER_PTR = 0xB5DD
PC_ROOM_HEADER_BANK = 0xB5E7
ROOM_COUNT = 296

HIGH_PALETTE_SLOTS = frozenset({0, 3, 4, 5})
FOLLOWER_DMA_SHEETS = frozenset({0xCB, 0xD7, 0xD9})


def parse_hex_int(value: str | int) -> int:
    """Parse hex ($23, 0x23) or decimal ints."""
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if s.startswith("$"):
        return int(s[1:], 16)
    return int(s, 0)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rom_bytes(path: Path) -> bytes:
    """Load an SFC/SMC ROM into unheadered LoROM byte space (read-only)."""
    raw = path.read_bytes()
    # Handle 512-byte SMC copier headers even on quirky trailing-byte donor ROMs.
    for off in (0, 512, len(raw) % 0x8000):
        if off + 0x8000 <= len(raw):
            title = raw[off + 0x7FC0:off + 0x7FC0 + 21]
            if sum(32 <= b < 127 for b in title) >= 16:
                return raw[off:]
    if len(raw) % 0x8000 == 512 and len(raw) > 512:
        return raw[512:]
    return raw


@contextmanager
def staged_ro_rom(src_path: Path):
    """Copy src_path into a scratch tempdir and assert source SHA-256 never mutates."""
    src_path = Path(src_path).expanduser().resolve()
    before = sha256_file(src_path)
    with tempfile.TemporaryDirectory(prefix="oos_ro_") as tmp:
        copy = Path(tmp) / "ro_copy.sfc"
        shutil.copyfile(src_path, copy)
        try:
            yield copy, before
        finally:
            after = sha256_file(src_path)
            if after != before:
                raise RuntimeError(
                    f"Source ROM mutated unexpectedly: {src_path} ({before[:12]} -> {after[:12]})"
                )


def snes_to_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


def read_u16(buf: bytes, off: int) -> int:
    return buf[off] | (buf[off + 1] << 8)


def bgr555_to_rgb(word: int) -> tuple[int, int, int]:
    """Convert SNES BGR555 15-bit word to 8-bit RGB."""
    r5 = word & 0x1F
    g5 = (word >> 5) & 0x1F
    b5 = (word >> 10) & 0x1F
    return ((r5 << 3) | (r5 >> 2), (g5 << 3) | (g5 >> 2), (b5 << 3) | (b5 >> 2))


def rgb_to_bgr555(rgb: tuple[int, int, int]) -> int:
    r, g, b = rgb
    return ((r >> 3) & 0x1F) | (((g >> 3) & 0x1F) << 5) | (((b >> 3) & 0x1F) << 10)


def _srgb_to_linear(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """Convert sRGB (0..255) to CIE L*a*b* (D65) for perceptual color matching."""
    r = _srgb_to_linear(rgb[0])
    g = _srgb_to_linear(rgb[1])
    b = _srgb_to_linear(rgb[2])
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0

    fx, fy, fz = f(x), f(y), f(z)
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def lab_distance(c1: tuple[float, float, float], c2: tuple[float, float, float]) -> float:
    """Weighted perceptual Lab distance (slightly prioritizes luminance & hue ramp integrity)."""
    dl = c1[0] - c2[0]
    da = c1[1] - c2[1]
    db = c1[2] - c2[2]
    return math.sqrt(1.15 * dl * dl + da * da + db * db)


def lz2_decompress(buf: bytes, start: int, *, big_endian: bool = False,
                   max_output: int = 0x10000) -> tuple[bytes, int]:
    """Decompress ALTTP LC-LZ2 / HyruleMagic stream (mode 0 sheet LE, mode 1 OW map BE)."""
    if not 0 <= start < len(buf):
        return b"", 0
    p = start
    out = bytearray()
    n = len(buf)
    while p < n:
        b = buf[p]
        p += 1
        if b == 0xFF:
            break
        cmd = b >> 5
        if cmd == 7:
            if p >= n:
                break
            cmd = (b >> 2) & 7
            ln = (((b & 3) << 8) | buf[p]) + 1
            p += 1
        else:
            ln = (b & 0x1F) + 1
        if len(out) + ln > max_output:
            break
        if cmd == 0:
            if p + ln > n:
                break
            out += buf[p:p + ln]
            p += ln
        elif cmd == 1:
            if p >= n:
                break
            out += bytes([buf[p]]) * ln
            p += 1
        elif cmd == 2:
            if p + 1 >= n:
                break
            a, c = buf[p], buf[p + 1]
            p += 2
            for k in range(ln):
                out.append(a if (k & 1) == 0 else c)
        elif cmd == 3:
            if p >= n:
                break
            a = buf[p]
            p += 1
            for k in range(ln):
                out.append((a + k) & 0xFF)
        else:
            if p + 1 >= n:
                break
            off = ((buf[p] << 8) | buf[p + 1]) if big_endian else (buf[p] | (buf[p + 1] << 8))
            p += 2
            for _ in range(ln):
                if off >= len(out):
                    out.append(0)
                else:
                    out.append(out[off])
                off += 1
    return bytes(out), p - start


def global_sheet_table(rom: bytes) -> tuple[list[int], int]:
    """Return ([bank_snes, hi_snes, lo_snes], sheet_count) for Oracle 255 or vanilla 223."""
    if len(rom) >= 0x120000:
        b23 = (snes_to_pc(0x23FD00), snes_to_pc(0x23FE00), snes_to_pc(0x23FF00))
        v0 = (snes_to_pc(0x00CF80), snes_to_pc(0x00D05F), snes_to_pc(0x00D13E))
        if all(off + EXTENDED_SHEET_COUNT <= len(rom) for off in b23):
            matches = sum(
                all(rom[b23[k] + i] == rom[v0[k] + i] for k in range(3))
                for i in range(VANILLA_SHEET_COUNT)
            )
            if matches >= 0xC0:
                return [0x23FD00, 0x23FE00, 0x23FF00], EXTENDED_SHEET_COUNT
    out = []
    for a, default in ((0x00E772, 0xCF80), (0x00E777, 0xD05F), (0x00E77C, 0xD13E)):
        i = snes_to_pc(a)
        if i + 3 < len(rom):
            op = rom[i]
            if op == 0xB9:
                addr = (rom[i + 1] | (rom[i + 2] << 8)) - 0x73
            elif op == 0xBF:
                addr = ((rom[i + 3] << 16) | rom[i + 1] | (rom[i + 2] << 8)) - 0x73
            else:
                addr = default
        else:
            addr = default
        out.append(addr)
    return out, VANILLA_SHEET_COUNT


def bpp_of_sheet(sid: int) -> int:
    return 2 if sid in (113, 114) or sid >= 218 else 3


def decode_chars(raw: bytes, bpp: int) -> list[tuple[int, ...]]:
    """Decode raw SNES 2bpp/3bpp tile buffer into list of 64-int 8x8 tiles."""
    sz = 24 if bpp == 3 else 16
    out: list[tuple[int, ...]] = []
    for t in range(len(raw) // sz):
        base = t * sz
        px: list[int] = []
        for y in range(8):
            p0 = raw[base + 2 * y]
            p1 = raw[base + 2 * y + 1]
            p2 = raw[base + 16 + y] if bpp == 3 else 0
            for x in range(8):
                b = 7 - x
                px.append(((p0 >> b) & 1) | (((p1 >> b) & 1) << 1) | (((p2 >> b) & 1) << 2))
        out.append(tuple(px))
    return out


def decode_sheet_chars(rom: bytes, sheet_ids: Iterable[int] | None = None) -> dict[int, list[tuple[int, ...]]]:
    """Decompress global graphics sheets -> dict[sid, list[64-int tile]]."""
    addrs, count = global_sheet_table(rom)
    tb, th, tl = (snes_to_pc(a) for a in addrs)
    wanted = set(sheet_ids) if sheet_ids is not None else set(range(count))
    res: dict[int, list[tuple[int, ...]]] = {}
    for g in sorted(wanted):
        if not (0 <= g < count) or tb + g >= len(rom):
            continue
        snes_addr = (rom[tb + g] << 16) | (rom[th + g] << 8) | rom[tl + g]
        off = snes_to_pc(snes_addr)
        if not (0 <= off < len(rom)):
            res[g] = []
            continue
        if 115 <= g <= 126:
            data = bytes(rom[off:off + 0x600])
        else:
            data, _ = lz2_decompress(rom, off, big_endian=False, max_output=0x1000)
        bpp = bpp_of_sheet(g)
        cap = 0x600 if bpp == 3 else 0x800
        res[g] = decode_chars(data[:cap], bpp)
    return res


def flip_tile8(px: tuple[int, ...] | list[int], hflip: bool = False, vflip: bool = False) -> tuple[int, ...]:
    if not hflip and not vflip:
        return tuple(px)
    rows = [tuple(px[i * 8:(i + 1) * 8]) for i in range(8)]
    if hflip:
        rows = [r[::-1] for r in rows]
    if vflip:
        rows = rows[::-1]
    return tuple(v for r in rows for v in r)


def canonical_tile8(px: Iterable[int], *, preserve_zero: bool = True) -> tuple[int, ...] | None:
    """Flip- & color-relabel-invariant key for an 8x8 tile. Returns None if flat."""
    seq = tuple(px)
    if len(seq) != 64:
        return None
    if len(set(seq)) <= 1:
        return None
    best: tuple[int, ...] | None = None
    for hf in (False, True):
        for vf in (False, True):
            tpx = flip_tile8(seq, hf, vf)
            if preserve_zero:
                mp = {0: 0}
                nxt = 1
                key_list = []
                for p in tpx:
                    if p not in mp:
                        mp[p] = nxt
                        nxt += 1
                    key_list.append(mp[p])
                k = tuple(key_list)
            else:
                mp = {}
                k = tuple(mp.setdefault(p, len(mp)) for p in tpx)
            if best is None or k < best:
                best = k
    return best


def zs_version(rom: bytes) -> int:
    if len(rom) <= PC_ZS_VERSION:
        return 0
    v = rom[PC_ZS_VERSION]
    return 0 if v == 0xFF else v


def area_parent_id(rom: bytes, area_id: int) -> int:
    v = zs_version(rom)
    if v >= 3 and len(rom) > PC_ZS_PARENT_EXPANDED + area_id and area_id < 0xA0:
        p = rom[PC_ZS_PARENT_EXPANDED + area_id]
        if p < 0xC0:
            return p
    if area_id < 0x80 and len(rom) > 0x125EC + (area_id & 0x3F):
        base = 0x40 if area_id >= 0x40 else 0x00
        return base + rom[0x125EC + (area_id & 0x3F)]
    return area_id


def load_area_static_graphics(rom: bytes, area_id: int) -> list[int]:
    """Return the 8 overworld static graphics sheet IDs for area_id (parent-resolved)."""
    parent = area_parent_id(rom, area_id)
    v = zs_version(rom)
    # Check native tail map directory first if available for $A0-$BF
    if area_id >= 0xA0:
        build_dir = REPO_ROOT / "Scripts" / "Build"
        if str(build_dir) not in os.sys.path:
            os.sys.path.insert(0, str(build_dir))
        try:
            import gfx_ledger
            tail = gfx_ledger.read_tail_areas(rom)
            if area_id in tail:
                return list(tail[area_id]["static_graphics"])
        except Exception:
            pass
    if v >= 3 and parent < 0xA0 and rom[PC_ZS_TILE_GFX_EN] not in (0, 0xFF):
        off = PC_ZS_TILE_GFX_ARR + parent * 8
        slots = list(rom[off:off + 8])
    elif parent < 0x80:
        iw = 0x20 if parent < 0x40 else 0x21
        slots = [rom[PC_GFX_GROUPS2 + iw * 8 + i] for i in range(8)]
        ag = rom[PC_AREA_GFX + parent]
        for k in range(4):
            val = rom[PC_GFX_GROUPS1 + ag * 4 + k]
            if val:
                slots[3 + k] = val
    else:
        slots = [0] * 8
    return slots


def load_area_animated_sheet(rom: bytes, area_id: int) -> int:
    parent = area_parent_id(rom, area_id)
    v = zs_version(rom)
    if v >= 3 and parent < 0xA0 and rom[PC_ZS_ANIM_GFX_EN] not in (0, 0xFF):
        val = rom[PC_ZS_ANIM_GFX_ARR + parent]
        if val not in (0, 0xFF):
            return val
    return 0x5B if parent < 0x40 else 0x5A


def load_overworld_slot_chars(rom: bytes, area_id: int,
                              all_sheets: dict[int, list[tuple[int, ...]]] | None = None
                              ) -> dict[int, list[tuple[int, ...]]]:
    """Return {slot_idx (0..7): 64-char list} applying slot-7 animated top-32 overlay."""
    slots = load_area_static_graphics(rom, area_id)
    anim = load_area_animated_sheet(rom, area_id)
    needed = set(slots) | {anim}
    sheets = all_sheets if all_sheets is not None else decode_sheet_chars(rom, needed)
    out: dict[int, list[tuple[int, ...]]] = {}
    blank = (0,) * 64
    for slot_idx, sid in enumerate(slots):
        base_chars = list(sheets.get(sid, []))
        while len(base_chars) < 64:
            base_chars.append(blank)
        if slot_idx == 7 and anim in sheets:
            anim_chars = sheets[anim]
            for c in range(min(32, len(anim_chars))):
                base_chars[c] = anim_chars[c]
        out[slot_idx] = base_chars[:64]
    return out


def decode_overworld_palette_128(rom: bytes, area_id: int) -> list[tuple[int, int, int]]:
    """Build 128-entry CGRAM palette matching ALTTP/ZSv3 Overworld rendering."""
    parent = area_parent_id(rom, area_id)
    v = zs_version(rom)
    world = 0 if parent < 0x40 else (1 if parent < 0x80 else 0)
    if parent in (3, 5, 7):
        world = 2
    elif parent in (0x43, 0x45, 0x47):
        world = 3
    if v >= 2 and parent < 0xA0 and rom[PC_ZS_MAIN_PAL_EN] not in (0, 0xFF):
        mp = rom[PC_ZS_MAIN_PAL_ARR + parent]
        if mp != 0xFF:
            world = mp

    ap = rom[PC_AREA_PAL + (parent if parent < 0x80 else 0)]
    p1, p2, p3 = (rom[PC_PAL_GROUP + ap * 4 + k] for k in range(3))

    pal128: list[tuple[int, int, int]] = [(0, 0, 0)] * 128
    # Rows 0..1: HUD palette (16 words per row at 0xDD660)
    if PC_HUD_PAL + 64 <= len(rom):
        for i in range(32):
            pal128[i] = bgr555_to_rgb(read_u16(rom, PC_HUD_PAL + 2 * i))

    # Rows 2..6 left half (cols 1..7): Overworld Main palette (35 colors)
    main_off = PC_OW_MAIN_PAL + world * 35 * 2
    main_cols = [bgr555_to_rgb(read_u16(rom, main_off + 2 * i)) for i in range(35)]
    for r in range(5):
        for c in range(7):
            pal128[(r + 2) * 16 + 1 + c] = main_cols[r * 7 + c]

    # Rows 2..4 & 5..7 right half (cols 9..15): Overworld Aux palettes (21 colors each)
    for idx, r0 in ((p1, 2), (p2, 5)):
        aux_off = PC_OW_AUX_PAL + min(idx, 19) * 21 * 2
        for r in range(3):
            for c in range(7):
                pal128[(r0 + r) * 16 + 9 + c] = bgr555_to_rgb(read_u16(rom, aux_off + 2 * (r * 7 + c)))

    # Row 7 left half (cols 1..7): Overworld Animated palette (7 colors)
    anim_off = PC_OW_ANIM_PAL + min(p3, 13) * 7 * 2
    for c in range(7):
        pal128[7 * 16 + 1 + c] = bgr555_to_rgb(read_u16(rom, anim_off + 2 * c))

    # Background BG0 color (area-specific BGR in ZSv2+ if enabled, else main[0])
    bg_rgb = main_cols[0]
    if v >= 2 and parent < 0xA0 and rom[PC_ZS_CUSTOM_BG_EN] not in (0, 0xFF):
        w = read_u16(rom, PC_ZS_CUSTOM_BG_PAL + parent * 2)
        if w != 0:
            bg_rgb = bgr555_to_rgb(w)
    for r in range(8):
        pal128[r * 16] = bg_rgb
        pal128[r * 16 + 8] = bg_rgb
    return pal128


def decode_dungeon_palette_128(rom: bytes, palette_set_id: int) -> list[tuple[int, int, int]]:
    """Build 128-entry dungeon CGRAM table via UnderworldPaletteSets -> Dec4B -> DD734."""
    pal_set = min(max(palette_set_id, 0), 71)
    set_off = rom[PC_PALETTESET_IDS + pal_set * 4]
    ptr_word = read_u16(rom, PC_DUN_PAL_PTR_TABLE + set_off)
    pal_idx = ptr_word // 180
    pal_off = PC_DUN_MAIN_PAL + pal_idx * 180
    pal128: list[tuple[int, int, int]] = [(0, 0, 0)] * 128
    if pal_off + 180 <= len(rom):
        for r in range(6):
            for c in range(15):
                pal128[(r + 2) * 16 + 1 + c] = bgr555_to_rgb(read_u16(rom, pal_off + 2 * (r * 15 + c)))
    return pal128


def ow_layout_flags(rom: bytes) -> tuple[bool, bool]:
    """Return (has_expanded_tile16, has_expanded_tile32) matching yaze overworld_layout.cc."""
    if len(rom) < 0x200000:
        return False, False
    v = zs_version(rom)
    if v == 0:
        return False, False
    supports_enum = v >= 3
    exp16 = supports_enum or rom[PC_MAP16_EXP_FLAG] != 0x0F
    exp32 = supports_enum or rom[PC_MAP32_EXP_FLAG] != 0x04
    return exp16, exp32


def decode_tile16_table(rom: bytes) -> list[tuple[int, int, int, int]]:
    """Return list of (tl_word, tr_word, bl_word, br_word) Tile16 quadrant words."""
    exp16, _ = ow_layout_flags(rom)
    base = PC_MAP16_EXPANDED if exp16 else PC_MAP16_VANILLA
    count = EXPANDED_TILE16_COUNT if exp16 else VANILLA_TILE16_COUNT
    out: list[tuple[int, int, int, int]] = []
    for i in range(count):
        off = base + i * 8
        if off + 8 > len(rom):
            break
        out.append((
            read_u16(rom, off),
            read_u16(rom, off + 2),
            read_u16(rom, off + 4),
            read_u16(rom, off + 6),
        ))
    return out


def decode_map32_table(rom: bytes) -> list[tuple[int, int, int, int]]:
    """Return list of (tl, tr, bl, br) Tile16 IDs for all Map32 definitions."""
    _, exp32 = ow_layout_flags(rom)
    addrs = PC_MAP32_EXPANDED if exp32 else PC_MAP32_VANILLA
    cnt = 0x67E0 if exp32 else 0x33F0
    out: list[tuple[int, int, int, int]] = []
    for i in range(0, cnt, 6):
        if any(a + i + 6 > len(rom) for a in addrs):
            break
        for k in range(4):
            qs = []
            lo_shift_off = 4 if k <= 1 else 5
            nibble_shift = 4 if (k % 2 == 0) else 0
            for d in range(4):
                a1 = rom[addrs[d] + k + i]
                a2 = rom[addrs[d] + i + lo_shift_off]
                qs.append(a1 | (((a2 >> nibble_shift) & 0x0F) << 8))
            out.append((qs[0], qs[1], qs[2], qs[3]))
    return out


def decode_overworld_map_grid(rom: bytes, area_id: int,
                              map32_table: list[tuple[int, int, int, int]] | None = None
                              ) -> list[list[int]]:
    """Decode one 32x32 Tile16 grid (one 512x512 screen) for Overworld map area_id."""
    if map32_table is None:
        map32_table = decode_map32_table(rom)
    if len(rom) > PC_TAIL_PTR_LO + area_id * 3 + 2 and rom[PC_TAIL_PTR_MARKER] == 0xEA:
        hi_base, lo_base = PC_TAIL_PTR_HI, PC_TAIL_PTR_LO
    else:
        hi_base, lo_base = PC_MAP32_PTR_HI, PC_MAP32_PTR_LO
    if hi_base + 3 * area_id + 3 > len(rom) or lo_base + 3 * area_id + 3 > len(rom):
        return [[0] * 32 for _ in range(32)]
    p1 = snes_to_pc(int.from_bytes(rom[hi_base + 3 * area_id:hi_base + 3 * area_id + 3], "little"))
    p2 = snes_to_pc(int.from_bytes(rom[lo_base + 3 * area_id:lo_base + 3 * area_id + 3], "little"))
    lo, _ = lz2_decompress(rom, p2, big_endian=True, max_output=512)
    hi, _ = lz2_decompress(rom, p1, big_endian=True, max_output=512)
    grid = [[0] * 32 for _ in range(32)]
    for idx in range(min(256, len(lo), len(hi))):
        tid = (hi[idx] << 8) | lo[idx]
        if tid < len(map32_table):
            tl, tr, bl, br = map32_table[tid]
            x, y = idx % 16, idx // 16
            grid[y * 2][x * 2] = tl
            grid[y * 2][x * 2 + 1] = tr
            grid[y * 2 + 1][x * 2] = bl
            grid[y * 2 + 1][x * 2 + 1] = br
    return grid


def decode_large_overworld_grid(rom: bytes, area_id: int) -> tuple[list[list[int]], str]:
    """Return full area grid (64x64 for Large, 64x32 Wide, 32x64 Tall, 32x32 Small) + size label."""
    parent = area_parent_id(rom, area_id)
    v = zs_version(rom)
    map32 = decode_map32_table(rom)
    if v >= 3 and parent < 0xA0 and len(rom) > 0x1788D + parent:
        sz = rom[0x1788D + parent]  # 0=Small, 1=Large, 2=Wide, 3=Tall
    elif parent < 0x80:
        b = rom[0x12844 + (parent & 0x3F)]
        sz = 1 if b != 0 else 0
    else:
        sz = 0
    if sz == 1:  # Large 2x2
        nw = decode_overworld_map_grid(rom, parent, map32)
        ne = decode_overworld_map_grid(rom, parent + 1, map32)
        sw = decode_overworld_map_grid(rom, parent + 8, map32)
        se = decode_overworld_map_grid(rom, parent + 9, map32)
        return [nw[r] + ne[r] for r in range(32)] + [sw[r] + se[r] for r in range(32)], "Large"
    if sz == 2:  # Wide 2x1
        w0 = decode_overworld_map_grid(rom, parent, map32)
        w1 = decode_overworld_map_grid(rom, parent + 1, map32)
        return [w0[r] + w1[r] for r in range(32)], "Wide"
    if sz == 3:  # Tall 1x2
        t0 = decode_overworld_map_grid(rom, parent, map32)
        t1 = decode_overworld_map_grid(rom, parent + 8, map32)
        return t0 + t1, "Tall"
    return decode_overworld_map_grid(rom, parent, map32), "Small"


def palette8_for_subpal(pal128: list[tuple[int, int, int]], pal_row: int,
                        high_half: bool) -> list[tuple[int, int, int]]:
    """Return 8-entry RGB list [bg0, c1..c7] for CGRAM row 0..7 and left/right half."""
    row = pal_row & 7
    half = 8 if high_half else 0
    base = row * 16 + half
    return [pal128[row * 16]] + [pal128[base + k] for k in range(1, 8)]


def render_tile8_rgba(px: Iterable[int], pal8: list[tuple[int, int, int]],
                      *, transparent_zero: bool = True) -> Image.Image:
    im = Image.new("RGBA", (8, 8))
    data = []
    for v in px:
        idx = v & 7
        if idx == 0 and transparent_zero:
            data.append((0, 0, 0, 0))
        else:
            r, g, b = pal8[idx]
            data.append((r, g, b, 255))
    im.putdata(data)
    return im


def render_tile16_rgba(words: tuple[int, int, int, int],
                       slot_chars: dict[int, list[tuple[int, ...]]],
                       pal128: list[tuple[int, int, int]],
                       *, transparent_zero: bool = False) -> Image.Image:
    """Render one 16x16 Tile16 faithfully honoring Tile8 ID, H/V flips, and subpalette."""
    bg = (0, 0, 0, 0) if transparent_zero else (*pal128[0], 255)
    canvas = Image.new("RGBA", (16, 16), bg)
    positions = ((0, 0), (8, 0), (0, 8), (8, 8))
    for w, (qx, qy) in zip(words, positions):
        ch_id = w & 0x3FF
        pal_row = (w >> 10) & 7
        hflip = bool((w >> 14) & 1)
        vflip = bool((w >> 15) & 1)
        slot = ch_id // 64
        local_chr = ch_id % 64
        px = slot_chars.get(slot, [(0,) * 64] * 64)[local_chr]
        px_tf = flip_tile8(px, hflip=hflip, vflip=vflip)
        pal8 = palette8_for_subpal(pal128, pal_row, high_half=(slot in HIGH_PALETTE_SLOTS))
        tile_im = render_tile8_rgba(px_tf, pal8, transparent_zero=transparent_zero)
        canvas.alpha_composite(tile_im, (qx, qy))
    return canvas


def read_room_header(rom: bytes, room_id: int) -> dict[str, int] | None:
    """Read dungeon room header directly from ROM (mirrors yaze Room::LoadHeader)."""
    if PC_ROOM_HEADER_PTR + 2 >= len(rom) or PC_ROOM_HEADER_BANK >= len(rom):
        return None
    hdr_ptr_snes = rom[PC_ROOM_HEADER_PTR] | (rom[PC_ROOM_HEADER_PTR + 1] << 8) | (rom[PC_ROOM_HEADER_PTR + 2] << 16)
    table_pc = snes_to_pc(hdr_ptr_snes) + room_id * 2
    if table_pc + 1 >= len(rom):
        return None
    bank = rom[PC_ROOM_HEADER_BANK]
    room_snes = (bank << 16) | read_u16(rom, table_pc)
    loc = snes_to_pc(room_snes)
    if loc < 0 or loc + 13 >= len(rom):
        return None
    b0 = rom[loc]
    return {
        "room_id": room_id,
        "header_pc": loc,
        "bg2": (b0 >> 5) & 0x07,
        "collision": (b0 >> 2) & 0x07,
        "is_dark": bool(b0 & 0x01),
        "palette": rom[loc + 1],
        "blockset": rom[loc + 2],
        "spriteset": rom[loc + 3],
        "effect": rom[loc + 4],
        "tag1": rom[loc + 5],
        "tag2": rom[loc + 6],
    }


def load_resource_labels(repo_root: Path = REPO_ROOT) -> dict[str, dict[str, str]]:
    """Load Oracle room, entrance, overworld_map, spriteset, and item labels."""
    res: dict[str, dict[str, str]] = {"room": {}, "overworld_map": {}, "entrance": {}, "sprite": {}}
    for rel in ("Docs/Dev/Planning/oracle_room_labels.json",
                "Docs/Dev/Planning/oracle_resource_labels.json"):
        p = repo_root / rel
        if not p.is_file():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        src = data.get("resource_labels", data)
        for cat in res:
            if isinstance(src.get(cat), dict):
                res[cat].update({str(k).lower(): str(v) for k, v in src[cat].items()})
    return res


def find_z3ed_bin(explicit: str | Path | None = None, repo_root: Path = REPO_ROOT) -> Path | None:
    """Resolve best available z3ed binary (explicit > OOS_Z3ED_BIN > locator > qualified > PATH)."""
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    if os.environ.get("OOS_Z3ED_BIN"):
        candidates.append(Path(os.environ["OOS_Z3ED_BIN"]).expanduser())
    # Qualified bundles & built worktrees ordered newest mtime first so Wave 1B wins automatically.
    discovered: list[Path] = []
    qual_dir = Path.home() / ".yaze" / "qualified"
    if qual_dir.is_dir():
        discovered.extend(p for p in qual_dir.glob("*/z3ed") if p.is_file())
    for wt_root in (repo_root.parent / "yaze-worktrees", Path.home() / "src/hobby/yaze-worktrees"):
        if wt_root.is_dir():
            discovered.extend(p for p in wt_root.glob("*/build*/**/z3ed") if p.is_file())
    discovered.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    candidates.extend(discovered)
    # Standard z3ed_locator.sh order fallback
    candidates.extend([
        repo_root.parent / "yaze/scripts/z3ed",
        Path.home() / "src/hobby/yaze/scripts/z3ed",
        Path.home() / "Applications/Yaze Nightly.app/Contents/MacOS/z3ed",
        Path.home() / ".local/yaze/nightly/current/z3ed",
        Path.home() / ".local/yaze/bin/z3ed",
        Path.home() / ".local/yaze/z3ed",
    ])
    on_path = shutil.which("z3ed")
    if on_path:
        candidates.append(Path(on_path))
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return c
    return None


def z3ed_supported_commands(z3ed_bin: Path | None) -> set[str]:
    if not z3ed_bin:
        return set()
    proc = subprocess.run([str(z3ed_bin), "--list-commands"], capture_output=True, text=True)
    if proc.returncode != 0:
        return set()
    cmds = set()
    for line in (proc.stdout + "\n" + proc.stderr).splitlines():
        s = line.strip()
        if not s or " " not in s:
            continue
        tok = s.split()[0]
        if "-" in tok or tok.isalnum():
            cmds.add(tok)
    return cmds


def run_z3ed_json(z3ed_bin: Path, args: list[str]) -> tuple[Any | None, str]:
    """Run a z3ed CLI command and extract its JSON object payload even with [INFO] log prefix."""
    proc = subprocess.run([str(z3ed_bin), *args], capture_output=True, text=True)
    text = proc.stdout.strip()
    start = text.find("{")
    if proc.returncode != 0 or start < 0:
        return None, (proc.stderr or proc.stdout).strip()
    try:
        return json.loads(text[start:]), proc.stderr.strip()
    except json.JSONDecodeError as exc:
        return None, f"json decode error: {exc}: {text[:160]}"
