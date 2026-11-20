#!/usr/bin/env python3
"""Unit tests for Scripts/Overworld/check_ow_grammar.py."""

from __future__ import annotations

import hashlib
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
for _rel in ("Scripts/Overworld", "Scripts/Build", "Scripts/Tools"):
    _p = str(REPO_ROOT / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_ow_grammar as cog  # noqa: E402
import check_sprite_sheet_compat as cssc  # noqa: E402
import check_tile16_pins as ctp  # noqa: E402
import scene_intent_common as sic  # noqa: E402


LIVE_ROM_PATH = Path(
    "/Users/scawful/Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj/rom"
)

# Canonical synthetic Tile16 IDs programmed into 0x1E8000 in SyntheticOwRomBuilder
TID_WALK = 0x000
TID_SOLID = 0x001
TID_SOLID_CURVE = 0x002  # Mixed quadrant (1,0,0,0) -> chamfered corner
TID_DEEP_WATER = 0x003
TID_SHALLOW_WATER = 0x004
TID_BUSH = 0x005
TID_LEDGE_S = 0x006
TID_TREE = 0x007  # Dash tree / hookshot 0x27 (excluded from EDGE-003 solid embed)
TID_LONELY_BUSH = 0x036  # LONELY_PROP_TILE16_IDS
TID_DOOR_LEFT = 0x00FB  # DOOR_HALF_TILES
TID_DOOR_RIGHT = 0x00FC
TID_SIGN = 0x101  # SIGN_TILE16_IDS
TID_SOIL = 0x3CD  # Walkable soil pad tile
TID_LADDER_CAP = 0x046D  # LADDER_CAP_TILE16_IDS (TT 0x22)
TID_LADDER_BODY = 0x0184  # LADDER_BODY_TILE16_IDS (TT 0x22)
TID_STAIR = 0x07E1  # Biome stone step Tile16 (TT 0x22, not a ladder)
TID_WALK_VAR_BASE = 0x010  # 32 varied walkable tiles (0x010..0x02F)


def _pc_to_snes(pc: int) -> int:
    bank = pc // 0x8000
    addr = 0x8000 + (pc % 0x8000)
    return (bank << 16) | addr


def _lz2_literals(data: bytes) -> bytes:
    out = bytearray()
    for i in range(0, len(data), 32):
        chunk = data[i : i + 32]
        out.append(len(chunk) - 1)  # cmd=0 (raw copy), length-1
        out.extend(chunk)
    out.append(0xFF)
    return bytes(out)


class SyntheticOwRomBuilder:
    """Minimal self-contained ZSOW v3 160-map LoROM image builder for tests."""

    def __init__(self) -> None:
        self.rom = bytearray(0x400000)
        self._map32_entries: list[tuple[int, int, int, int]] = [(0, 0, 0, 0)]
        self._map32_index: dict[tuple[int, int, int, int], int] = {(0, 0, 0, 0): 0}
        self._data_cursor = 0x220000
        self._spr_cursor = 0x48010

        # ZSOW v3 flags + expanded Tile16 / Map32 markers
        self.rom[sic.PC_ZS_VERSION] = 3
        self.rom[sic.PC_ZS_MAIN_PAL_EN] = 1
        self.rom[sic.PC_ZS_OVERLAY_EN] = 1
        self.rom[sic.PC_ZS_TILE_GFX_EN] = 1
        self.rom[sic.PC_ZS_ANIM_GFX_EN] = 1
        self.rom[ctp.TILE16_EXP_FLAG_PC] = 0x3D
        self.rom[ctp.MAP32_EXP_FLAG_PC] = 0x00

        # Character -> TileType defaults (chars 0..10)
        char_types = {
            0: 0x00,  # walkable
            1: 0x01,  # solid
            2: 0x08,  # deep_water
            3: 0x09,  # shallow_water
            4: 0x50,  # interactive (bush/rock)
            5: 0x28,  # N ledge
            6: 0x29,  # S ledge
            7: 0x2A,  # E ledge
            8: 0x2B,  # W ledge
            9: 0x27,  # dash tree
            10: 0x22,  # ladder / stairs
        }
        for ch, tt in char_types.items():
            self.rom[sic.PC_TILETYPE + ch] = tt

        # Register synthetic Tile16 definitions
        self._set_tile16(TID_WALK, (0, 0, 0, 0))
        self._set_tile16(TID_SOLID, (1, 1, 1, 1))
        self._set_tile16(TID_SOLID_CURVE, (1, 0, 0, 0))
        self._set_tile16(TID_DEEP_WATER, (2, 2, 2, 2))
        self._set_tile16(TID_SHALLOW_WATER, (3, 3, 3, 3))
        self._set_tile16(TID_BUSH, (4, 4, 4, 4))
        self._set_tile16(TID_LONELY_BUSH, (4, 4, 4, 4))
        self._set_tile16(TID_SIGN, (4, 4, 4, 4))
        self._set_tile16(TID_LEDGE_S, (6, 6, 6, 6))
        self._set_tile16(TID_TREE, (9, 9, 9, 9))
        self._set_tile16(TID_DOOR_LEFT, (1, 1, 1, 1))
        self._set_tile16(TID_DOOR_RIGHT, (1, 1, 1, 1))
        self._set_tile16(TID_SOIL, (0, 0, 0, 0))
        self._set_tile16(TID_LADDER_CAP, (10, 10, 10, 10))
        self._set_tile16(TID_LADDER_BODY, (10, 10, 10, 10))
        self._set_tile16(TID_STAIR, (10, 10, 10, 10))
        for offset in range(32):
            self._set_tile16(TID_WALK_VAR_BASE + offset, (0, 0, 0, 0))

        # Sprite blocksets:
        #   0: valid 3bpp sprite sheets (128,129,130,131) -> bytes 13,14,15,16
        #   1: different valid 3bpp sprite sheets missing 128 -> bytes 17,18,19,20
        #   2: invalid 2bpp sheet 218 in slot 0 -> byte (218 - 0x73 = 103)
        self._set_blockset(0, (13, 14, 15, 16))
        self._set_blockset(1, (17, 18, 19, 20))
        self._set_blockset(2, (103, 14, 15, 16))

        # Default parents (small 1x1), empty sprite terminator at $09:8000 (PC 0x48000)
        self.rom[0x48000] = 0xFF
        for m in range(160):
            self.rom[sic.PC_ZS_PARENT_EXPANDED + m] = m
            self.rom[0x1788D + m] = 0
            for base in (0x141438, 0x141578, 0x1416B8):
                self._write_u16(base + m * 2, 0x8000)

        # Deactivate all exits ($00..$4E) and entrances (0..128)
        for i in range(0x4F):
            self._write_u16(0x16051 + i * 2, 0xFFFF)
            self._write_u16(0x160EF + i * 2, 0xFFFF)
        for i in range(129):
            self._write_u16(0x0DB96F + i * 2, 0xFFFF)
            self._write_u16(0x0DBA71 + i * 2, 0xFFFF)
            self.rom[0x0DBB73 + i] = 0xFF

        # Initialize all 160 screens with varied floor so barren/monotone doesn't fire unexpectedly
        self._default_snes_pair: tuple[int, int] | None = None
        varied = self.make_varied_floor()
        for m in range(160):
            if m == 0:
                self.set_screen(m, varied)
            else:
                # Reuse compressed Map32 streams for untouched background maps
                self._assign_map32_snes(m, *self._default_snes_pair)

    def _write_u16(self, pc: int, val: int) -> None:
        self.rom[pc] = val & 0xFF
        self.rom[pc + 1] = (val >> 8) & 0xFF

    def _write_u24(self, pc: int, val: int) -> None:
        self.rom[pc] = val & 0xFF
        self.rom[pc + 1] = (val >> 8) & 0xFF
        self.rom[pc + 2] = (val >> 16) & 0xFF

    def _set_tile16(self, tid: int, words: tuple[int, int, int, int]) -> None:
        pc = ctp.TILE16_EXPANDED_PC + tid * 8
        for i, w in enumerate(words):
            self._write_u16(pc + i * 2, w)

    def _set_blockset(self, bs: int, vals: tuple[int, int, int, int]) -> None:
        pc = cssc.SPRITE_BLOCKSET_PC + bs * 4
        for i, v in enumerate(vals):
            self.rom[pc + i] = v

    @staticmethod
    def make_uniform_grid(tid: int = TID_WALK) -> list[list[int]]:
        return [[tid] * 32 for _ in range(32)]

    @staticmethod
    def make_varied_floor(base_tid: int = TID_WALK_VAR_BASE) -> list[list[int]]:
        grid = [[base_tid + ((x * 7 + y * 5) % 32) for x in range(32)] for y in range(32)]
        grid[1][1] = TID_SIGN  # Give screen a focal sign anchor by default
        return grid

    def _alloc_map32(self, quad: tuple[int, int, int, int]) -> int:
        idx = self._map32_index.get(quad)
        if idx is None:
            idx = len(self._map32_entries)
            self._map32_entries.append(quad)
            self._map32_index[quad] = idx
            g = idx // 4
            s = idx % 4
            for qi, base in enumerate(ctp.MAP32_EXPANDED_PCS):
                p = base + g * 6
                val = quad[qi]
                self.rom[p + s] = val & 0xFF
                hi = (val >> 8) & 0x0F
                if s == 0:
                    self.rom[p + 4] = (self.rom[p + 4] & 0x0F) | (hi << 4)
                elif s == 1:
                    self.rom[p + 4] = (self.rom[p + 4] & 0xF0) | hi
                elif s == 2:
                    self.rom[p + 5] = (self.rom[p + 5] & 0x0F) | (hi << 4)
                else:
                    self.rom[p + 5] = (self.rom[p + 5] & 0xF0) | hi
        return idx

    def _alloc_data(self, payload: bytes) -> int:
        # Keep chunk inside single LoROM 32KB bank
        rem = 0x8000 - (self._data_cursor % 0x8000)
        if len(payload) > rem:
            self._data_cursor += rem
        pc = self._data_cursor
        self.rom[pc : pc + len(payload)] = payload
        self._data_cursor += len(payload)
        return _pc_to_snes(pc)

    def _assign_map32_snes(self, map_id: int, hi_snes: int, lo_snes: int) -> None:
        self._write_u24(ctp.MAP32_PTR_HI_PC + map_id * 3, hi_snes)
        self._write_u24(ctp.MAP32_PTR_LO_PC + map_id * 3, lo_snes)

    def set_screen(self, map_id: int, grid: list[list[int]]) -> None:
        hi = bytearray(256)
        lo = bytearray(256)
        for idx in range(256):
            x, y = (idx & 15) * 2, (idx >> 4) * 2
            quad = (
                grid[y][x],
                grid[y][x + 1],
                grid[y + 1][x],
                grid[y + 1][x + 1],
            )
            t32 = self._alloc_map32(quad)
            hi[idx] = (t32 >> 8) & 0xFF
            lo[idx] = t32 & 0xFF
        hi_snes = self._alloc_data(_lz2_literals(bytes(hi)))
        lo_snes = self._alloc_data(_lz2_literals(bytes(lo)))
        if self._default_snes_pair is None:
            self._default_snes_pair = (hi_snes, lo_snes)
        self._assign_map32_snes(map_id, hi_snes, lo_snes)

    def set_sprites(self, map_id: int, phase: int, entries: list[tuple[int, int, int]]) -> None:
        ptrs = (0x141438, 0x141578, 0x1416B8)
        pc = self._spr_cursor
        for x, y, sid in entries:
            self.rom[pc] = y & 0xFF
            self.rom[pc + 1] = x & 0xFF
            self.rom[pc + 2] = sid & 0xFF
            pc += 3
        self.rom[pc] = 0xFF
        self._spr_cursor = pc + 1
        snes_addr = _pc_to_snes(pc - len(entries) * 3) & 0xFFFF
        self._write_u16(ptrs[phase] + map_id * 2, snes_addr)

    def set_exit(self, idx: int, map_id: int, local_tx: int, local_ty: int, room: int = 0x01) -> None:
        par = self.rom[sic.PC_ZS_PARENT_EXPANDED + map_id]
        lm = par & 0x3F
        ox, oy = (lm % 8) * 512, (lm // 8) * 512
        # foot_tile_x = (xp - ox + 8) // 16 ; foot_tile_y = (yp - oy + 16) // 16
        xp = (ox + local_tx * 16) & 0xFFFF
        yp = (oy + (local_ty - 1) * 16) & 0xFFFF
        self._write_u16(0x15D8A + idx * 2, room)
        self.rom[0x15E28 + idx] = map_id
        self._write_u16(0x16051 + idx * 2, yp)
        self._write_u16(0x160EF + idx * 2, xp)

    def set_entrance(self, idx: int, map_id: int, local_tx: int, local_ty: int, eid: int = 0x10) -> None:
        self._write_u16(0x0DB96F + idx * 2, map_id)
        cell = (local_ty * 64 + local_tx) * 2
        self._write_u16(0x0DBA71 + idx * 2, cell)
        self.rom[0x0DBB73 + idx] = eid

    def set_area_meta(
        self,
        map_id: int,
        *,
        main_pal: int | None = None,
        pal_set: int | None = None,
        aux_pal: tuple[int, int] | None = None,
        mosaic: int | None = None,
        overlay: int | None = None,
        area_gfx: int | None = None,
        gfx8: tuple[int, ...] | None = None,
        music_p1: int | None = None,
        spr_gfx: tuple[int, int, int] | None = None,
        spr_pal: tuple[int, int, int] | None = None,
    ) -> None:
        if main_pal is not None:
            self.rom[sic.PC_ZS_MAIN_PAL_ARR + map_id] = main_pal
        if pal_set is not None:
            self.rom[0x4C635 + map_id] = pal_set
            if aux_pal is not None:
                pg = sic.PC_PAL_GROUP + pal_set * 4
                self.rom[pg] = aux_pal[0]
                self.rom[pg + 1] = aux_pal[1]
        if mosaic is not None:
            self.rom[0x140200 + map_id] = mosaic
        if overlay is not None:
            self._write_u16(sic.PC_ZS_OVERLAY_ARR + map_id * 2, overlay)
        if area_gfx is not None:
            self.rom[sic.PC_AREA_GFX + map_id] = area_gfx
        if gfx8 is not None:
            for k, val in enumerate(gfx8):
                self.rom[sic.PC_ZS_TILE_GFX_ARR + map_id * 8 + k] = val
        if music_p1 is not None and map_id < 0x40:
            self.rom[0x14303 + map_id + 1 * 0x40] = music_p1
        if spr_gfx is not None:
            for ph, val in enumerate(spr_gfx):
                if map_id < 0x40:
                    self.rom[cssc.OW_SPR_GFX_PC + map_id + ph * 0x40] = val
                elif map_id < 0x80:
                    self.rom[cssc.OW_SPR_GFX_PC + map_id + 0x80] = val
                else:
                    self.rom[cssc.SW_SPR_GFX_PC + (map_id - 0x80)] = val
        if spr_pal is not None:
            for ph, val in enumerate(spr_pal):
                if map_id < 0x40:
                    self.rom[cssc.OW_SPR_PAL_PC + map_id + ph * 0x40] = val
                elif map_id < 0x80:
                    self.rom[cssc.OW_SPR_PAL_PC + map_id + 0x80] = val
                else:
                    self.rom[cssc.SW_SPR_PAL_PC + (map_id - 0x80)] = val

    def build(self) -> bytes:
        return bytes(self.rom)


def _rules(report: dict) -> list[str]:
    return [f["rule_id"] for f in report["findings"]]


class TestOwGrammarRules(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_clean_exemplar_map_has_zero_findings(self) -> None:
        b = SyntheticOwRomBuilder()
        g = b.make_varied_floor()
        # Add an organic curved stone outcrop (chamfered with TID_SOLID_CURVE corners)
        for y in range(6, 10):
            for x in range(10, 15):
                g[y][x] = TID_SOLID
        g[6][10] = TID_SOLID_CURVE
        g[6][14] = TID_SOLID_CURVE
        g[9][10] = TID_SOLID_CURVE
        g[9][14] = TID_SOLID_CURVE
        # Framed cave entrance at (12, 9) with solid backdrop north and walkable doormat south
        b.set_entrance(0, 0x00, 12, 9, eid=0x11)
        # Grouped 2x2 bush cluster near outcrop
        g[11][17] = TID_BUSH
        g[11][18] = TID_BUSH
        g[12][17] = TID_BUSH
        g[12][18] = TID_BUSH
        b.set_screen(0x00, g)
        b.set_sprites(0x00, 1, [(20, 20, 0x07)])  # BeanVendor Day
        b.set_sprites(0x00, 2, [(20, 20, 0x07)])  # BeanVendor Night
        rep = cog.audit_overworld_grammar(b.build(), maps_spec="0x00", root=self.tmp_root)
        self.assertEqual(rep["total_findings"], 0, rep["findings"])

    def test_lane_001_sustained_choke_vs_widened_corridor(self) -> None:
        b = SyntheticOwRomBuilder()
        g = b.make_varied_floor()
        # 12-tile-long 1-tile-wide vertical corridor along x=15 (y=4..15)
        for y in range(4, 16):
            g[y][14] = TID_SOLID
            g[y][16] = TID_SOLID
        b.set_screen(0x00, g)
        rep = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00", rule_prefixes={"LANE-001"}, root=self.tmp_root
        )
        self.assertEqual(_rules(rep), ["LANE-001"])

        # Widening one wall to 2 tiles eliminates the sustained >=10-tile 1-tile bottleneck
        for y in range(4, 16):
            g[y][16] = TID_WALK
        b.set_screen(0x00, g)
        rep_wide = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00", rule_prefixes={"LANE-001"}, root=self.tmp_root
        )
        self.assertEqual(rep_wide["total_findings"], 0)

    def test_lane_002_sealed_walkable_pocket(self) -> None:
        b = SyntheticOwRomBuilder()
        g = b.make_varied_floor()
        for y in range(10, 17):
            for x in range(10, 17):
                if y in (10, 16) or x in (10, 16):
                    g[y][x] = TID_SOLID
        b.set_screen(0x00, g)
        rep = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00", rule_prefixes={"LANE-002"}, root=self.tmp_root
        )
        self.assertEqual(_rules(rep), ["LANE-002"])

        # Opening a 1-tile gate connects the pocket to the map border component
        g[10][13] = TID_WALK
        b.set_screen(0x00, g)
        rep_open = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00", rule_prefixes={"LANE-002"}, root=self.tmp_root
        )
        self.assertEqual(rep_open["total_findings"], 0)

    def test_lane_003_narrow_sea_channel_on_permitted_seam(self) -> None:
        b = SyntheticOwRomBuilder()
        # 0x98 <-> 0x99 are horizontal neighbors with DEFAULT_LYRA_EDGE_PERMS = 0x0F
        g98 = b.make_uniform_grid(TID_DEEP_WATER)
        g99 = b.make_uniform_grid(TID_DEEP_WATER)
        for y in range(32):
            g98[y][31] = TID_SOLID
            g99[y][0] = TID_SOLID
        # Open only 1 tile (2 subtiles < 4) across seam -> LANE-003
        g98[15][31] = TID_DEEP_WATER
        g99[15][0] = TID_DEEP_WATER
        b.set_screen(0x98, g98)
        b.set_screen(0x99, g99)
        rep = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x98", rule_prefixes={"LANE-003"}, root=self.tmp_root
        )
        self.assertEqual(_rules(rep), ["LANE-003"])

        # Open second row (4 water subtiles) -> clears LANE-003
        g98[16][31] = TID_DEEP_WATER
        g99[16][0] = TID_DEEP_WATER
        b.set_screen(0x98, g98)
        b.set_screen(0x99, g99)
        rep_ok = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x98", rule_prefixes={"LANE-003"}, root=self.tmp_root
        )
        self.assertEqual(rep_ok["total_findings"], 0)

    def test_curv_001_boxy_solid_rect_vs_chamfered(self) -> None:
        b = SyntheticOwRomBuilder()
        g = b.make_varied_floor()
        for y in range(8, 14):
            for x in range(8, 14):
                g[y][x] = TID_SOLID
        b.set_screen(0x00, g)
        rep = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00", rule_prefixes={"CURV-001"}, root=self.tmp_root
        )
        self.assertEqual(_rules(rep), ["CURV-001"])

        # Chamfer outer corners with mixed-quadrant tile -> clears CURV-001
        g[8][8] = TID_SOLID_CURVE
        g[8][13] = TID_SOLID_CURVE
        g[13][8] = TID_SOLID_CURVE
        g[13][13] = TID_SOLID_CURVE
        b.set_screen(0x00, g)
        rep_curved = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00", rule_prefixes={"CURV-001"}, root=self.tmp_root
        )
        self.assertEqual(rep_curved["total_findings"], 0)

    def test_curv_002_long_flat_wall(self) -> None:
        b = SyntheticOwRomBuilder()
        g = b.make_varied_floor()
        for x in range(4, 24):  # 20 identical solid tiles horizontally
            g[6][x] = TID_SOLID
        b.set_screen(0x00, g)
        rep = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00", rule_prefixes={"CURV-002"}, root=self.tmp_root
        )
        self.assertEqual(_rules(rep), ["CURV-002"])

    def test_curv_003_twin_islands_and_box_island(self) -> None:
        b = SyntheticOwRomBuilder()
        g_twin = b.make_uniform_grid(TID_DEEP_WATER)
        for y in range(4, 10):
            for x in range(4, 10):
                g_twin[y][x] = TID_WALK
                g_twin[y][x + 14] = TID_WALK
        b.set_screen(0x00, g_twin)
        rep_twin = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00", rule_prefixes={"CURV-003"}, root=self.tmp_root
        )
        self.assertEqual(_rules(rep_twin), ["CURV-003"])
        self.assertIn("twin_islands", rep_twin["findings"][0]["finding_key"])

        b2 = SyntheticOwRomBuilder()
        g_box = b2.make_uniform_grid(TID_DEEP_WATER)
        for y in range(6, 18):  # 12x12 rectangular block (144 tiles, rect_ratio=1.0)
            for x in range(6, 18):
                g_box[y][x] = TID_WALK
        b2.set_screen(0x00, g_box)
        rep_box = cog.audit_overworld_grammar(
            b2.build(), maps_spec="0x00", rule_prefixes={"CURV-003"}, root=self.tmp_root
        )
        self.assertEqual(_rules(rep_box), ["CURV-003"])
        self.assertIn("box_island", rep_box["findings"][0]["finding_key"])

    def test_curv_004_checkerboard_and_curv_005_uncapped_band(self) -> None:
        b = SyntheticOwRomBuilder()
        g = b.make_uniform_grid(TID_DEEP_WATER)
        for x in range(4, 15, 2):
            g[5][x] = TID_SOLID  # #W#W#W teeth on row 5
        for x in range(10, 16):
            g[20][x] = TID_SOLID  # uncapped 6-tile mid-screen horizontal cliff
        b.set_screen(0x00, g)
        # Put floor around row 20 so uncapped band has walkable on N/S/W/E
        for y in (19, 21):
            for x in range(9, 17):
                g[y][x] = TID_WALK
        g[20][9] = TID_WALK
        g[20][16] = TID_WALK
        b.set_screen(0x00, g)
        rep = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00", rule_prefixes={"CURV-004", "CURV-005"}, root=self.tmp_root
        )
        self.assertEqual(sorted(_rules(rep)), ["CURV-004", "CURV-005"])

    def test_prop_001_002_003_and_land_002(self) -> None:
        b = SyntheticOwRomBuilder()
        # Isolated bushes (3x 0x036 -> WARN PROP-001) while signs (0x101) are ignored
        g = b.make_varied_floor()
        g[5][5] = TID_LONELY_BUSH
        g[10][10] = TID_LONELY_BUSH
        g[15][15] = TID_LONELY_BUSH
        b.set_screen(0x00, g)

        # Sea screen with 1 lonely rock + barren monotone (>= 85% single tile, <= 30 uniq, no signs)
        g_sea = b.make_uniform_grid(TID_DEEP_WATER)
        g_sea[12][12] = TID_SOLID
        b.set_screen(0x02, g_sea)

        rep0 = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00", rule_prefixes={"PROP-001"}, root=self.tmp_root
        )
        self.assertEqual(_rules(rep0), ["PROP-001"])
        self.assertEqual(rep0["findings"][0]["severity"], "WARN")

        rep2 = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x02", rule_prefixes={"PROP-002", "PROP-003", "LAND-002"}, root=self.tmp_root
        )
        self.assertEqual(sorted(_rules(rep2)), ["LAND-002", "PROP-002", "PROP-003"])

    def test_seam_001_to_004_continuity_and_mosaic_rules(self) -> None:
        b = SyntheticOwRomBuilder()
        # Seam 0x00 <-> 0x01 (horizontal):
        # Row 2..3 open walkable across seam (4 subtiles), Row 4..5 mismatch (walkable vs solid -> SEAM-001),
        # Also open enough subtiles (make rows 2..10 walkable = 18 subtiles >= 16) + mismatched main_pal/aux_pal/music -> SEAM-003 + SEAM-004
        g0 = b.make_varied_floor()
        g1 = b.make_varied_floor()
        # Block seam rows 11..31 identically with solid so only rows 2..10 + 0..1 are open (wait: let's keep 0..10 open = 22 subtiles, block 11..31 with solid except row 15 mismatched)
        for y in range(11, 32):
            g0[y][31] = TID_SOLID
            g1[y][0] = TID_SOLID
        g0[15][31] = TID_WALK
        g1[15][0] = TID_SOLID
        b.set_screen(0x00, g0)
        b.set_screen(0x01, g1)
        b.set_area_meta(0x00, main_pal=0x00, pal_set=0, aux_pal=(0x01, 0x02), area_gfx=0x01, music_p1=0x12, mosaic=0x00)
        b.set_area_meta(0x01, main_pal=0x02, pal_set=1, aux_pal=(0x03, 0x04), area_gfx=0x02, music_p1=0x32, mosaic=0x00)

        rep = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00", rule_prefixes={"SEAM"}, root=self.tmp_root
        )
        rids = set(_rules(rep))
        self.assertIn("SEAM-001", rids)
        self.assertIn("SEAM-003", rids)
        self.assertIn("SEAM-004", rids)

        # Snow overlay ($0095) without main_pal/gfx change skips SEAM-003 auto-mosaic check
        b2 = SyntheticOwRomBuilder()
        b2.set_screen(0x00, b2.make_varied_floor())
        b2.set_screen(0x01, b2.make_varied_floor())
        b2.set_area_meta(0x00, main_pal=0x00, overlay=0x0095, mosaic=0x00)
        b2.set_area_meta(0x01, main_pal=0x00, overlay=0x00FF, mosaic=0x00)
        rep_snow = cog.audit_overworld_grammar(
            b2.build(), maps_spec="0x00", rule_prefixes={"SEAM-003"}, root=self.tmp_root
        )
        self.assertEqual(rep_snow["total_findings"], 0)

    def test_edge_001_002_003_004_and_land_001(self) -> None:
        b = SyntheticOwRomBuilder()
        g = b.make_varied_floor()
        # Solid wall at (10,10) with embedded BlueSoldier (0x41) -> EDGE-003,
        # while Raven (0x00) or sprite on dash-tree 0x27 (TID_TREE) is allowed.
        g[10][10] = TID_SOLID
        g[11][10] = TID_SOLID
        g[12][10] = TID_SOLID
        g[11][11] = TID_TREE
        g[12][31] = TID_DOOR_LEFT  # Flush door half on east external seam of 0x00? Wait: 0x00 has same-world neighbor 0x01; make 0x01 have parent 0x01 -> ext_right is True!
        b.set_screen(0x00, g)
        b.set_sprites(0x00, 1, [
            (47, 18, 0x41),  # OOB sprite on 32x32 map 0x00 -> EDGE-002
            (10, 10, 0x41),  # Ground sprite inside pure solid -> EDGE-003
            (10, 10, 0x00),  # Raven (NON_GROUND_SPRITES) -> exempt
            (11, 11, 0x41),  # Ground sprite on dash tree 0x27 -> exempt
        ])
        # Exit 0 landing on blocked solid (10,10) -> EDGE-001
        b.set_exit(0, 0x00, 10, 10)
        # Entrance 0 flush on external North seam (y=0) in open field -> EDGE-004 + LAND-001
        b.set_entrance(0, 0x00, 20, 0, eid=0x15)

        rep = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00", rule_prefixes={"EDGE", "LAND-001"}, root=self.tmp_root
        )
        rids = set(_rules(rep))
        self.assertIn("EDGE-001", rids)
        self.assertIn("EDGE-002", rids)
        self.assertIn("EDGE-003", rids)
        self.assertIn("EDGE-004", rids)
        self.assertIn("LAND-001", rids)
        # Verify Raven & dash-tree soldier did not trigger EDGE-003
        edge3 = [f for f in rep["findings"] if f["rule_id"] == "EDGE-003"]
        self.assertEqual(len(edge3), 1)
        self.assertIn("(10,10)", edge3[0]["location"])

    def test_spr_001_002_003_004_rules(self) -> None:
        b = SyntheticOwRomBuilder()
        g = b.make_varied_floor()
        b.set_screen(0x00, g)
        # Map 0x00:
        # - SPR-001: spr_gfx[1]=1 (blockset 1 lacks sheet 128 needed by BlueSoldier 0x41), plus spr_pal=0x25 OOB (>= $14)
        # - SPR-002: SeaZora/WaterTektite 0x81 on dry ground
        # - SPR-004: BeanVendor 0x07 only in p1, missing in p2
        b.set_area_meta(0x00, spr_gfx=(0, 1, 0), spr_pal=(0x00, 0x25, 0x00))
        b.set_sprites(0x00, 1, [(10, 10, 0x41), (12, 12, 0x81), (14, 14, 0x07)])
        # Map 0x02: Phase palette parity drift across identical sprites (p1=0x01, p2=0x03) -> SPR-003
        b.set_area_meta(0x02, spr_gfx=(0, 0, 0), spr_pal=(0x01, 0x01, 0x03))
        b.set_sprites(0x02, 1, [(10, 10, 0x41)])
        b.set_sprites(0x02, 2, [(10, 10, 0x41)])
        # Sky map 0x8C colliding MainPal 0x05 with Kalyxo map 0x05 -> SPR-004
        b.set_area_meta(0x05, main_pal=0x05)
        b.set_area_meta(0x8C, main_pal=0x05)

        rep = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00,0x02,0x8C", rule_prefixes={"SPR"}, root=self.tmp_root
        )
        rids = set(_rules(rep))
        self.assertIn("SPR-001", rids)
        self.assertIn("SPR-002", rids)
        self.assertIn("SPR-003", rids)
        self.assertIn("SPR-004", rids)
        mainpal_hits = [f for f in rep["findings"] if f["rule_id"] == "SPR-004" and "main_pal_collision" in f["finding_key"]]
        self.assertEqual(len(mainpal_hits), 1)
        self.assertEqual(mainpal_hits[0]["map_id"], "0x8C")

    def test_int_001_bean_spots_and_int_002_ledge_landing(self) -> None:
        b = SyntheticOwRomBuilder()
        # Mock bean_vendor.asm in isolated tmp_root with 4 spots; spots 0..3 on map 0x00/0x02
        bean_asm = self.tmp_root / "Sprites" / "NPCs" / "bean_vendor.asm"
        bean_asm.parent.mkdir(parents=True, exist_ok=True)
        bean_asm.write_text(
            "MagicBeanSpot_Screens:\n"
            "  db $00, $02, $00, $02\n"
            "MagicBeanSpot_HomeXLo:\n"
            "  db $80, $80, $40, $40\n"
            "MagicBeanSpot_HomeXHi:\n"
            "  db $00, $00, $00, $00\n"
            "MagicBeanSpot_HomeYLo:\n"
            "  db $80, $80, $40, $40\n"
            "MagicBeanSpot_HomeYHi:\n"
            "  db $00, $00, $00, $00\n"
            "MagicBean_LegXSpeed:\n"
            "  db 0,0,0, 0,0,0, 0,0,0, 0,0,0\n"
            "MagicBean_LegYSpeed:\n"
            "  db 0,0,0, 0,0,0, 0,0,0, 0,0,0\n"
            "MagicBean_LegTimers:\n"
            "  db 0,0,0, 0,0,0, 0,0,0, 0,0,0\n",
            encoding="utf-8",
        )
        # Spot 0 & 2 on map 0x00: tile (8,8) clean 2x2 TID_SOIL + p1/p2 BeanVendor 0x07 -> Spot 0/2 clean;
        # Spot 1 & 3 on map 0x02: tile (8,8) is solid & missing BeanVendor in p2 -> INT-001 errors!
        # Also on map 0x00 place south ledge at (20,5) jumping into 8 solid tiles -> INT-002,
        # and at (24,5) jumping over 2 solid cliff tiles onto walkable -> no INT-002!
        g0 = b.make_varied_floor()
        g0[8][8] = TID_SOIL
        g0[8][9] = TID_SOIL
        g0[9][8] = TID_SOIL
        g0[9][9] = TID_SOIL
        g0[4][4] = TID_SOIL
        g0[4][5] = TID_SOIL
        g0[5][4] = TID_SOIL
        g0[5][5] = TID_SOIL
        # Bad ledge at (20,5) -> 8 solid tiles below
        g0[5][20] = TID_LEDGE_S
        for y in range(6, 14):
            g0[y][20] = TID_SOLID
        # Valid 2-tile cliff ledge at (24,5) -> 2 solid tiles, then walkable
        g0[5][24] = TID_LEDGE_S
        g0[6][24] = TID_SOLID
        g0[7][24] = TID_SOLID
        b.set_screen(0x00, g0)
        b.set_sprites(0x00, 1, [(8, 8, 0x07), (4, 4, 0x07)])
        b.set_sprites(0x00, 2, [(8, 8, 0x07), (4, 4, 0x07)])

        g2 = b.make_varied_floor()
        g2[8][8] = TID_SOLID
        b.set_screen(0x02, g2)
        b.set_sprites(0x02, 1, [(8, 8, 0x07)])  # p2 missing BeanVendor!

        rep0 = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00", rule_prefixes={"INT"}, root=self.tmp_root
        )
        self.assertEqual(_rules(rep0), ["INT-002"])
        self.assertIn("(20,5)", rep0["findings"][0]["location"])

        rep2 = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x02", rule_prefixes={"INT-001"}, root=self.tmp_root
        )
        self.assertTrue(any(f["rule_id"] == "INT-001" for f in rep2["findings"]))
        self.assertTrue(any("vendor_missing" in f["finding_key"] for f in rep2["findings"]))
        self.assertTrue(any("soil_pad" in f["finding_key"] for f in rep2["findings"]))

    def test_stair_001_short_vs_tall_ladders_and_stair_replacement(self) -> None:
        b = SyntheticOwRomBuilder()

        # 1. Kalyxo map 0x00: 1-tile short ladder at (6, 8) + 2-tile short 2x2 ladder at (14, 14)
        g0 = b.make_varied_floor()
        g0[8][6] = TID_LADDER_BODY
        for x in (14, 15):
            g0[14][x] = TID_LADDER_CAP
            g0[15][x] = TID_LADDER_BODY
        # Also a 1-tile trapped artifact inside solid wall at (24, 6) (no passable top/bot)
        g0[5][24] = TID_SOLID
        g0[6][24] = TID_LADDER_BODY
        g0[7][24] = TID_SOLID
        b.set_screen(0x00, g0)

        # 2. Kalyxo map 0x01: 3-tile tall genuine climb (2x3) -> MUST pass clean
        g1 = b.make_varied_floor()
        for x in (10, 11):
            g1[10][x] = TID_LADDER_CAP
            g1[11][x] = TID_LADDER_BODY
            g1[12][x] = TID_LADDER_BODY
        b.set_screen(0x01, g1)

        # 3. Eon Abyss 0x40: 2-tile ladder -> excluded from STAIR-001 scope
        g40 = b.make_varied_floor()
        g40[12][12] = TID_LADDER_CAP
        g40[13][12] = TID_LADDER_BODY
        b.set_screen(0x40, g40)

        # 4. Special OW 0x81 + 0x89: 3-tile tall cross-seam ladder (0x81 y=31 + 0x89 y=0..1) -> MUST pass clean
        g81 = b.make_varied_floor()
        g89 = b.make_varied_floor()
        g81[31][10] = TID_LADDER_CAP
        g89[0][10] = TID_LADDER_BODY
        g89[1][10] = TID_LADDER_BODY
        # Plus a 2-tile short ladder on 0x81 at (20, 18) -> flagged on Special OW
        g81[18][20] = TID_LADDER_CAP
        g81[19][20] = TID_LADDER_BODY
        b.set_screen(0x81, g81)
        b.set_screen(0x89, g89)

        rom_bytes = b.build()

        rep_all = cog.audit_overworld_grammar(
            rom_bytes, maps_spec="0x00,0x01,0x40,0x81,0x89", rule_prefixes={"STAIR-001"}, root=self.tmp_root
        )
        self.assertEqual([f["finding_key"] for f in rep_all["findings"]], [
            "STAIR-001.map_0x00.short_ladder_14_14",
            "STAIR-001.map_0x00.short_ladder_6_8",
            "STAIR-001.map_0x81.short_ladder_20_18",
        ])
        self.assertTrue(all(f["severity"] == "WARN" for f in rep_all["findings"]))

        # Filtering to the bottom seam screen 0x89 alone must still see 0x81(y=31) -> 0 warnings!
        rep_seam = cog.audit_overworld_grammar(
            rom_bytes, maps_spec="0x89", rule_prefixes={"STAIR-001"}, root=self.tmp_root
        )
        self.assertEqual(rep_seam["findings"], [])

        # Replace short ladders on 0x00 & 0x81 with biome stair TID_STAIR -> clears STAIR-001
        g0[8][6] = TID_STAIR
        for x in (14, 15):
            g0[14][x] = TID_STAIR
            g0[15][x] = TID_STAIR
        g81[18][20] = TID_STAIR
        g81[19][20] = TID_STAIR
        b.set_screen(0x00, g0)
        b.set_screen(0x81, g81)

        rep_clean = cog.audit_overworld_grammar(
            b.build(), maps_spec="0x00,0x01,0x40,0x81,0x89", rule_prefixes={"STAIR-001"}, root=self.tmp_root
        )
        self.assertEqual(rep_clean["findings"], [])


class TestOwGrammarCliAndRatchet(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run_cli(self, *args: str) -> tuple[int, str, str]:
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        with mock.patch.object(cog, "ROOT", self.tmp_dir), redirect_stdout(out_buf), redirect_stderr(err_buf):
            rc = cog.main(list(args))
        return rc, out_buf.getvalue(), err_buf.getvalue()

    def test_baseline_ratchet_write_forgive_resolve_and_regression(self) -> None:
        b = SyntheticOwRomBuilder()
        g = b.make_varied_floor()
        g[10][10] = TID_SOLID
        g[11][10] = TID_SOLID
        g[12][10] = TID_SOLID
        g[5][5] = TID_LONELY_BUSH
        b.set_screen(0x00, g)
        b.set_exit(0, 0x00, 10, 10)  # ERROR: EDGE-001 blocked exit
        rom_path = self.tmp_dir / "test.sfc"
        rom_path.write_bytes(b.build())

        base_path = self.tmp_dir / "baseline.json"
        out_json = self.tmp_dir / "report.json"
        out_md = self.tmp_dir / "report.md"

        # 1. Without baseline: ERROR causes exit code 1, --write-baseline captures snapshot
        rc1, stdout1, _ = self._run_cli(
            "--rom", str(rom_path), "--maps", "0x00", "--json",
            "--write-baseline", str(base_path),
            "--out-json", str(out_json), "--out-md", str(out_md),
        )
        self.assertEqual(rc1, 1)
        data1 = json.loads(stdout1)
        self.assertGreaterEqual(data1["error_count"], 1)
        self.assertTrue(base_path.is_file())
        self.assertTrue(out_json.is_file())
        self.assertIn("Scawful Overworld Design Grammar Report", out_md.read_text(encoding="utf-8"))

        # 2. Same ROM against saved baseline -> all baselined, new_count=0, rc=0
        rc2, stdout2, _ = self._run_cli(
            "--rom", str(rom_path), "--maps", "0x00", "--json",
            "--baseline", str(base_path),
        )
        self.assertEqual(rc2, 0)
        data2 = json.loads(stdout2)
        self.assertEqual(data2["new_count"], 0)
        self.assertEqual(data2["baselined_count"], data1["total_findings"])
        self.assertEqual(data2["resolved_count"], 0)

        # 3. Fix exit on 0x00 -> resolved_count increases, still rc=0
        b.set_exit(0, 0x00, 20, 20)
        rom_path.write_bytes(b.build())
        rc3, stdout3, _ = self._run_cli(
            "--rom", str(rom_path), "--maps", "0x00", "--json",
            "--baseline", str(base_path),
        )
        self.assertEqual(rc3, 0)
        data3 = json.loads(stdout3)
        self.assertGreaterEqual(data3["resolved_count"], 1)

        # 4. Introduce a new WARN (CURV-001 boxy rock) -> rc=0 normally, rc=1 with --strict
        g2 = b.make_varied_floor()
        for y in range(15, 21):
            for x in range(15, 21):
                g2[y][x] = TID_SOLID
        b.set_screen(0x00, g2)
        rom_path.write_bytes(b.build())

        rc4, stdout4, _ = self._run_cli(
            "--rom", str(rom_path), "--maps", "0x00", "--json",
            "--baseline", str(base_path),
        )
        self.assertEqual(rc4, 0)
        data4 = json.loads(stdout4)
        self.assertTrue(any(f["rule_id"] == "CURV-001" for f in data4["new_findings"]))

        rc4_strict, _, _ = self._run_cli(
            "--rom", str(rom_path), "--maps", "0x00", "--strict",
            "--baseline", str(base_path),
        )
        self.assertEqual(rc4_strict, 1)

        # 5. Introduce new ERROR (OOB sprite) -> rc=1 even with baseline
        b.set_sprites(0x00, 1, [(50, 10, 0x41)])
        rom_path.write_bytes(b.build())
        rc5, stdout5, _ = self._run_cli(
            "--rom", str(rom_path), "--maps", "0x00", "--json",
            "--baseline", str(base_path),
        )
        self.assertEqual(rc5, 1)
        data5 = json.loads(stdout5)
        self.assertTrue(any(f["rule_id"] == "EDGE-002" for f in data5["new_findings"]))

    def test_map_spec_presets_ranges_and_error_exit_codes(self) -> None:
        self.assertEqual(len(cog.parse_map_spec("kalyxo", 192)), 64)
        self.assertEqual(cog.parse_map_spec("abyss", 192), set(range(0x40, 0x80)))
        self.assertEqual(cog.parse_map_spec("special", 192), set(range(0x80, 0xC0)))
        self.assertEqual(cog.parse_map_spec("0x0A,0x1C-0x1D,$92", 192), {0x0A, 0x1C, 0x1D, 0x92})
        with self.assertRaises(ValueError):
            cog.parse_map_spec("0x20-0x10", 192)
        with self.assertRaises(ValueError):
            cog.parse_map_spec("0xFF", 192)

        rc_missing, _, err = self._run_cli("--rom", str(self.tmp_dir / "nope.sfc"))
        self.assertEqual(rc_missing, 2)
        self.assertIn("ROM not found", err)

        b = SyntheticOwRomBuilder()
        rom_path = self.tmp_dir / "tiny.sfc"
        rom_path.write_bytes(b.build())
        rc_bad_maps, _, _ = self._run_cli("--rom", str(rom_path), "--maps", "0x1D-0x1C")
        self.assertEqual(rc_bad_maps, 2)

        # --min-severity ERROR filters out INFO/WARN
        g = b.make_varied_floor()
        g[5][5] = TID_LONELY_BUSH
        g[10][10] = TID_LONELY_BUSH
        g[15][15] = TID_LONELY_BUSH  # emits WARN PROP-001, zero ERRORs
        b.set_screen(0x00, g)
        rom_path.write_bytes(b.build())
        rc_min, out_min, _ = self._run_cli(
            "--rom", str(rom_path), "--maps", "0x00", "--min-severity", "ERROR", "--json"
        )
        self.assertEqual(rc_min, 0)
        self.assertEqual(json.loads(out_min)["total_findings"], 0)

    @unittest.skipUnless(LIVE_ROM_PATH.is_file(), "Live .yazeproj ROM not present")
    def test_live_rom_read_only_192_smoke(self) -> None:
        before = hashlib.sha256(LIVE_ROM_PATH.read_bytes()).hexdigest()
        rom = sic.load_rom_bytes(LIVE_ROM_PATH)
        rep = cog.audit_overworld_grammar(rom, maps_spec="0x92", rom_path=str(LIVE_ROM_PATH))
        after = hashlib.sha256(LIVE_ROM_PATH.read_bytes()).hexdigest()
        self.assertEqual(before, after)
        self.assertEqual(rep["maps_capacity"], 192)
        self.assertEqual(rep["maps_checked"], 1)


if __name__ == "__main__":
    unittest.main()
