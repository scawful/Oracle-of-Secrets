#!/usr/bin/env python3
"""D8 sky-fill transfer and BG1 placement checks.

Models SkyRoom_Classify, SkyRoom_ArmLayer and the two-pass BG1 fill in
Dungeons/sky_room_sky.asm. The model is pinned to the source lists, the
subscreen table and the cloud lattice, so a drift in those bytes fails here.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKY = (ROOT / "Dungeons" / "sky_room_sky.asm").read_text(encoding="utf-8")
DATA = (ROOT / "Dungeons" / "sky_room_sky_data.asm").read_text(encoding="utf-8")

OPEN_ROOMS = (0x90, 0x91, 0x92, 0x93, 0x94, 0x95, 0xA0, 0xB0, 0xA7)
ENCLOSED_ROOMS = (0x8C, 0x96, 0xA6, 0x9B, 0x9C, 0x9D)
# Header layer type ($0414) after Underworld_LoadHeader, before ArmLayer.
# Taken from the read-only yaze ROM audit (dungeon-room-header).
HEADER_LAYER = {
    0x8C: 0x03,
    0x90: 0x01, 0x91: 0x01, 0x92: 0x01, 0x93: 0x01, 0x94: 0x01, 0x95: 0x01,
    0x96: 0x06,
    0x9B: 0x00, 0x9C: 0x00, 0x9D: 0x00,
    0xA0: 0x01, 0xA6: 0x00, 0xA7: 0x01, 0xB0: 0x01,
}
PLAIN_SKY = 0x1D80
BLANK = 0x01E9
PIT = 0x01E9


def _dw_list(label: str, end: str) -> tuple[int, ...]:
    body = SKY.split(f"{label}:", 1)[1].split(f"{end}:", 1)[0]
    words = [int(tok, 16) for tok in re.findall(r"\$([0-9A-Fa-f]+)", body)]
    return tuple(words)


def _subscreen() -> tuple[int, ...]:
    body = SKY.split("SkyRoom_Subscreen:", 1)[1].split("SkyRoom_List:", 1)[0]
    return tuple(int(tok, 16) for tok in re.findall(r"\$([0-9A-Fa-f]+)", body))


def _clouds() -> list[tuple[int, int]]:
    rows = []
    for line in DATA.splitlines():
        match = re.search(r"dw\s+\$([0-9A-Fa-f]+)\s*:\s*db\s+\$([0-9A-Fa-f]+)", line)
        if match:
            rows.append((int(match.group(1), 16), int(match.group(2), 16)))
    return rows


OPEN = _dw_list("SkyRoom_List", "SkyRoom_List_end")
ENCLOSED = _dw_list("SkyRoom_Enclosed", "SkyRoom_Enclosed_end")
SUBSCREEN = _subscreen()
CLOUDS = _clouds()


def classify(room: int) -> int:
    if room in OPEN:
        return 1
    if room in ENCLOSED:
        return 2
    return 0


def cloud_word(tile_byte: int) -> int:
    return (PLAIN_SKY | (tile_byte & 0x3F)) | ((tile_byte & 0xC0) << 8)


def fill_bg1(bg2: list[int]) -> list[int]:
    """Two-pass fill. bg2 is 0x1000 tilemap words (the $7E2000 buffer)."""
    bg1 = [0] * 0x1000
    for index, word in enumerate(bg2):
        char = word & 0x03FF
        if char == PIT or 0x01DB <= char <= 0x01DF:
            bg1[index] = PLAIN_SKY
        else:
            bg1[index] = BLANK
    for offset, tile_byte in CLOUDS:
        stamped = cloud_word(tile_byte)
        cursor = offset
        for delta in (0x0000, 0x0040, 0x0FC0, 0x0040):
            cursor += delta
            if not 0 <= cursor < 0x2000 or cursor & 1:
                raise AssertionError(f"cloud copy ${cursor:04X} leaves the BG1 buffer")
            cell = cursor >> 1
            if bg1[cell] != BLANK:
                bg1[cell] = stamped
    return bg1


class LayerState:
    def __init__(self, **kw):
        self.layer = kw.get("layer", 1)
        self.cgwsel = kw.get("cgwsel", 0x00)
        self.cgadsub = kw.get("cgadsub", 0x60)
        self.tm = kw.get("tm", 0x17)
        self.ts = kw.get("ts", 0x00)
        self.e2 = kw.get("e2", 0x0000)
        self.e0 = kw.get("e0", 0x0000)
        self.e8 = kw.get("e8", 0x0000)
        self.e6 = kw.get("e6", 0x0000)
        self.bg1_h = kw.get("bg1_h", 0x0000)
        self.bg1_v = kw.get("bg1_v", 0x0000)
        self.frac_x = kw.get("frac_x", 0x4000)
        self.frac_y = kw.get("frac_y", 0x4000)
        self.effect = kw.get("effect", 0x05)
        self.off_x = kw.get("off_x", 0x0010)
        self.off_y = kw.get("off_y", 0x0020)

    def arm(self, kind: int) -> None:
        """SkyRoom_ArmLayer, including the open-room promote to layer 6."""
        if kind == 1:
            self.layer = 0x06
        layer = self.layer & 0xFF
        if layer < 8:
            sub = SUBSCREEN[layer]
            if sub & 0x80:
                self.tm, self.ts = 0x17, 0x00
            else:
                self.tm, self.ts = 0x16, sub
        self.cgwsel = 0x02
        if layer == 0x00:
            self.cgadsub = 0x20
        elif layer == 0x07:
            self.cgadsub = 0x32
        elif layer == 0x04:
            self.cgadsub = 0x62
        else:
            self.cgadsub = 0x20
        self.frac_x = 0
        self.frac_y = 0
        if kind == 1:
            self.effect = 0
            self.off_x = 0
            self.off_y = 0
        self.e0 = self.e2
        self.bg1_h = self.e2
        self.e6 = self.e8
        self.bg1_v = self.e8


def load_room(room: int, state: LayerState, bg2: list[int] | None, bg1: list[int]) -> int:
    """What SkyRoom_LoadRoom does after Underworld_LoadRoom returns."""
    kind = classify(room)
    if kind == 0:
        return kind
    # LoadHeader has already stored the header layer.
    state.layer = HEADER_LAYER[room]
    state.arm(kind)
    if kind == 1:
        filled = fill_bg1(bg2 or [0] * 0x1000)
        bg1[:] = filled
    return kind


class SkyRoomSourceTests(unittest.TestCase):
    def test_room_lists_match_the_d8_split(self):
        self.assertEqual(OPEN, OPEN_ROOMS)
        self.assertEqual(ENCLOSED, ENCLOSED_ROOMS)
        self.assertEqual(set(OPEN) & set(ENCLOSED), set())

    def test_subscreen_table_matches_vanilla(self):
        self.assertEqual(SUBSCREEN, (0x00, 0x01, 0x01, 0xFF, 0x01, 0x01, 0x01, 0x01))

    def test_arm_layer_is_on_the_load_path(self):
        body = SKY.split("SkyRoom_LoadRoom:", 1)[1].split("SkyRoom_Classify:", 1)[0]
        self.assertIn("JSR SkyRoom_Classify", body)
        self.assertIn("JSR SkyRoom_ArmLayer", body)
        arm = SKY.split("SkyRoom_ArmLayer:", 1)[1].split("SkyRoom_Subscreen:", 1)[0]
        self.assertIn("STA.l $7E0414", arm)
        self.assertIn("LDA.b #$06", arm)
        self.assertIn("STA.b $9A", arm)
        self.assertIn("STA.b $E0", arm)
        self.assertIn("STA.l $7E0120", arm)
        self.assertIn("STA.l $7E0620", arm)

    def test_callers_still_jsl_the_same_hook(self):
        for site in ("$028CE5", "$029407", "$02C583"):
            self.assertIn(f"org {site} : JSL SkyRoom_LoadRoom", SKY)
        followers = (ROOT / "Sprites" / "NPCs" / "followers.asm").read_text(encoding="utf-8")
        self.assertIn("JML SkyRoom_LoadRoom", followers)


class SkyRoomFillTests(unittest.TestCase):
    def test_cloud_lattice_stays_inside_four_quadrants(self):
        self.assertEqual(len(CLOUDS), 370)
        for offset, _tile in CLOUDS:
            cursor = offset
            for delta in (0x0000, 0x0040, 0x0FC0, 0x0040):
                cursor += delta
                self.assertLess(cursor, 0x2000)
                self.assertEqual(cursor & 1, 0)

    def test_pit_and_pit_lip_get_plain_sky_and_floor_is_cleared(self):
        bg2 = [0x0000] * 0x1000
        bg2[0] = PIT
        bg2[1] = 0x09DB
        bg2[2] = 0x49DE
        bg2[3] = 0x89DF
        bg2[4] = 0xC9DF
        bg2[5] = 0x01DA  # one below the lip range
        bg2[6] = 0x01E0  # one above the lip range
        bg2[7] = 0x11E9  # $1E9 with palette bits
        bg1 = fill_bg1(bg2)
        for index in (0, 1, 2, 3, 4, 7):
            self.assertNotEqual(bg1[index], BLANK, hex(index))
        self.assertEqual(bg1[5], BLANK)
        self.assertEqual(bg1[6], BLANK)
        self.assertEqual(bg1[8], BLANK)

    def test_clouds_stamp_only_sky_cells_and_all_four_copies(self):
        bg2 = [0x0000] * 0x1000
        offset, tile_byte = CLOUDS[0]
        copies = []
        cursor = offset
        for delta in (0x0000, 0x0040, 0x0FC0, 0x0040):
            cursor += delta
            copies.append(cursor >> 1)
        covered = set()
        for base, _tile in CLOUDS:
            cursor = base
            for delta in (0x0000, 0x0040, 0x0FC0, 0x0040):
                cursor += delta
                covered.add(cursor >> 1)
        for cell in copies:
            bg2[cell] = PIT
        plain = next(index for index in range(0x1000) if index not in covered)
        bg2[plain] = PIT
        bg1 = fill_bg1(bg2)
        stamped = cloud_word(tile_byte)
        for cell in copies:
            self.assertEqual(bg1[cell], stamped)
        self.assertEqual(bg1[plain], PLAIN_SKY)

    def test_enclosed_load_does_not_rewrite_bg1(self):
        sentinel = [0xABCD] * 0x1000
        state = LayerState()
        kind = load_room(0x8C, state, [PIT] * 0x1000, sentinel)
        self.assertEqual(kind, 2)
        self.assertEqual(sentinel, [0xABCD] * 0x1000)


class SkyRoomTransferTests(unittest.TestCase):
    def test_open_room_promotes_layer_and_syncs_scroll(self):
        state = LayerState(layer=0x01, cgadsub=0x60, cgwsel=0x00, tm=0x17, ts=0x00,
                           e2=0x0100, e0=0x0080, e8=0x0200, e6=0x0100)
        bg1 = [0] * 0x1000
        kind = load_room(0x90, state, [PIT] + [0] * 0x0FFF, bg1)
        self.assertEqual(kind, 1)
        self.assertEqual(state.layer, 0x06)
        self.assertEqual(state.cgwsel, 0x02)
        self.assertEqual(state.cgadsub, 0x20)
        self.assertEqual((state.tm, state.ts), (0x16, 0x01))
        self.assertEqual(state.e0, state.e2)
        self.assertEqual(state.e6, state.e8)
        self.assertEqual(state.bg1_h, state.e2)
        self.assertEqual(state.bg1_v, state.e8)
        self.assertEqual(state.frac_x, 0)
        self.assertEqual(state.frac_y, 0)
        self.assertEqual(state.effect, 0)
        self.assertEqual(state.off_x, 0)
        self.assertEqual(bg1[0] & 0x03FF, 0x0180)

    def test_every_open_room_uses_the_same_register_contract(self):
        for room in OPEN:
            state = LayerState(e2=0x0040, e8=0x0080, e0=0, e6=1)
            load_room(room, state, None, [0] * 0x1000)
            self.assertEqual(state.layer, 0x06, hex(room))
            self.assertEqual(state.cgadsub, 0x20, hex(room))
            self.assertEqual(state.ts, 0x01, hex(room))
            self.assertEqual(state.e0, 0x0040, hex(room))
            self.assertEqual(state.e6, 0x0080, hex(room))

    def test_open_to_enclosed_restores_layer3_main_screen(self):
        """$8C is layer 3: BG1 returns to the main screen and the subscreen drops."""
        state = LayerState()
        load_room(0x90, state, None, [0] * 0x1000)
        self.assertEqual(state.ts, 0x01)
        load_room(0x8C, state, None, [0] * 0x1000)
        self.assertEqual(state.layer, 0x03)
        self.assertEqual((state.tm, state.ts), (0x17, 0x00))
        self.assertEqual(state.cgadsub, 0x20)
        self.assertEqual(state.cgwsel, 0x02)

    def test_enclosed_to_open_clears_parallax_on_both_axes(self):
        """A stair or pit can arrive with only one axis already copied."""
        state = LayerState(e2=0x0300, e0=0x0300, e8=0x0180, e6=0x00C0, cgadsub=0xB3)
        load_room(0x9B, state, None, [0] * 0x1000)
        self.assertEqual(state.layer, 0x00)
        self.assertEqual(state.ts, 0x00)
        self.assertEqual(state.e6, 0x0180)
        # $96 keeps a moving-floor effect the header stored in $0428.
        state.effect = 0x05
        state.off_x = 0x0010
        load_room(0x96, state, None, [0] * 0x1000)
        self.assertEqual(state.layer, 0x06)
        self.assertEqual(state.effect, 0x05)
        self.assertEqual(state.off_x, 0x0010)
        self.assertEqual(state.ts, 0x01)
        load_room(0xA7, state, None, [0] * 0x1000)
        self.assertEqual(state.effect, 0)
        self.assertEqual(state.off_x, 0)
        self.assertEqual(state.e0, state.e2)
        self.assertEqual(state.e6, state.e8)

    def test_non_d8_room_is_left_alone(self):
        state = LayerState(cgadsub=0x62, e0=0x11, e2=0x22)
        bg1 = [0x1111] * 0x1000
        kind = load_room(0x00, state, [PIT] * 0x1000, bg1)
        self.assertEqual(kind, 0)
        self.assertEqual(state.cgadsub, 0x62)
        self.assertEqual(state.e0, 0x11)
        self.assertEqual(bg1[0], 0x1111)

    def test_entrance_bypass_still_arms_color_math(self):
        """Stairs, pits and door loads do not pass through entrance $29."""
        for room, caller in ((0x90, "special"), (0x95, "stairs"), (0xB0, "door")):
            state = LayerState(cgwsel=0x00, cgadsub=0xB3, tm=0x17, ts=0x00)
            load_room(room, state, None, [0] * 0x1000)
            self.assertEqual(state.cgwsel, 0x02, caller)
            self.assertEqual(state.cgadsub, 0x20, caller)
            self.assertEqual(state.ts, 0x01, caller)


if __name__ == "__main__":
    unittest.main()
