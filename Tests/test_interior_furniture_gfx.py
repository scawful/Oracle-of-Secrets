#!/usr/bin/env python3
"""Tile-word and BG-sheet invariants for interior timber windows and furniture.

The wall words are the live-ROM timber set (mullions $091/$093, glass
$0AC-$0AE on palette 3). Slot 2 is the underworld high palette half, so a
palette-0/1 word or a glass char on palette 2 is a broken window. Furniture
bins keep their verified palette rows and the furnace/chair mirrors.
"""
from __future__ import annotations

import json
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WALLS = ROOT / "Dungeons" / "house_walls.asm"
BINS = ROOT / "Dungeons" / "Objects" / "Data"
SHEETS = ROOT / "Data" / "graphics" / "dungeon_bg_sheets.json"

# Column-major words for objects $100-$103, $001-$002, and $061-$062.
CORNERS = [
    0x0894, 0x0893, 0x0892, 0x0893, 0x0891, 0x089E, 0x0898, 0x0899,
    0x0890, 0x0896, 0x08A6, 0x08A5, 0x0891, 0x0897, 0x08A3, 0x0CAE,
    0x0892, 0x0893, 0x0892, 0x8894, 0x0898, 0x0899, 0x889E, 0x8891,
    0x08A4, 0x88A6, 0x8896, 0x8890, 0x8CAE, 0x88A3, 0x8897, 0x8891,
    0x0890, 0x0896, 0x08A2, 0x4CAE, 0x0891, 0x0897, 0x48A6, 0x48A5,
    0x0890, 0x489E, 0x4898, 0x4899, 0x4894, 0x4893, 0x4892, 0x4893,
    0xCCAE, 0x88A2, 0x8896, 0x8890, 0x48A4, 0xC8A6, 0x8897, 0x8891,
    0x4898, 0x4899, 0xC89E, 0x8890, 0x4892, 0x4893, 0x4892, 0xC894,
]
TOP = [
    0x0890, 0x0896, 0x08A2, 0x0CAC, 0x0891, 0x0897, 0x08A3, 0x4CAC,
    0x8CAC, 0x88A2, 0x8896, 0x8890, 0xCCAC, 0x88A3, 0x8897, 0x8891,
]
LEFT = [
    0x0892, 0x0898, 0x08A4, 0x0CAD, 0x0893, 0x0899, 0x08A5, 0x8CAD,
    0x4CAD, 0x48A4, 0x4898, 0x4892, 0xCCAD, 0x48A5, 0x4899, 0x4893,
]
GLASS = {0x0AC, 0x0AD, 0x0AE}


def _words_after(text: str, org: str, count: int) -> list[int]:
    match = re.search(rf"org \${org}\b(.*?)(?=\norg |\nassert |\Z)", text, re.S)
    if match is None:
        raise AssertionError(f"missing org ${org}")
    words = []
    for line in match.group(1).splitlines():
        code = line.split(";", 1)[0]
        if "dw " not in code:
            continue
        words.extend(int(v, 16) for v in re.findall(r"\$([0-9A-Fa-f]+)", code))
    if len(words) != count:
        raise AssertionError(f"org ${org}: expected {count} words, got {len(words)}")
    return words


def _decode_bin(path: Path) -> list[tuple[int, list[int]]]:
    raw = path.read_bytes()
    words = list(struct.unpack("<" + "H" * (len(raw) // 2), raw[: len(raw) // 2 * 2]))
    rows = []
    i = 0
    while i < len(words):
        header = words[i]
        if header == 0:
            if any(w != 0 for w in words[i:]):
                raise AssertionError(f"{path.name}: data after terminator")
            return rows
        width = header & 0x1F
        if width == 0 or i + 1 + width > len(words):
            raise AssertionError(f"{path.name}: bad header ${header:04X} at {i}")
        rows.append((header, words[i + 1 : i + 1 + width]))
        i += 1 + width
    raise AssertionError(f"{path.name}: missing terminator")


def _palette(word: int) -> int:
    return (word >> 10) & 7


def _char(word: int) -> int:
    return word & 0x3FF


class InteriorWallWords(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WALLS.read_text()
        cls.corners = _words_after(cls.text, "00A6B8", 64)
        cls.top = _words_after(cls.text, "009E3A", 16)
        cls.left = _words_after(cls.text, "009E1A", 16)

    def test_tables_match_timber_window_set(self):
        self.assertEqual(self.corners, CORNERS)
        self.assertEqual(self.top, TOP)
        self.assertEqual(self.left, LEFT)

    def test_mullions_were_not_replaced_by_beam_flips(self):
        # The beam table wrote $4890 / $0892 here and the north windows closed.
        self.assertEqual(self.top[4], 0x0891)
        self.assertEqual(self.top[15], 0x8891)
        self.assertEqual(self.left[4], 0x0893)
        self.assertEqual(self.left[15], 0x4893)

    def test_palette_rows_and_slot(self):
        for word in self.corners + self.top + self.left:
            char = _char(word)
            pal = _palette(word)
            self.assertTrue(0x80 <= char <= 0xBF, f"${word:04X} left slot 2")
            if char in GLASS:
                self.assertEqual(pal, 3, f"glass ${word:04X} must use palette 3")
            else:
                self.assertEqual(pal, 2, f"frame ${word:04X} must use palette 2")


class InteriorFurnitureBins(unittest.TestCase):
    def test_furnace_is_palette_2_and_mirrored(self):
        rows = _decode_bin(BINS / "furnace.bin")
        self.assertEqual(len(rows), 4)
        for header, tiles in rows:
            self.assertEqual(header, 0x8004)
            self.assertEqual(len(tiles), 4)
            for word in tiles:
                self.assertEqual(_palette(word), 2)
                self.assertTrue(0x180 <= _char(word) <= 0x1BF)
            self.assertEqual(tiles[2], tiles[1] | 0x4000)
            self.assertEqual(tiles[3], tiles[0] | 0x4000)
            self.assertEqual(tiles[0] & 0x4000, 0)
            self.assertEqual(tiles[1] & 0x4000, 0)

    def test_ice_chair_is_palette_2_and_mirrored(self):
        rows = _decode_bin(BINS / "ice_chair.bin")
        self.assertEqual([(h, t) for h, t in rows], [
            (0x8002, [0x0986, 0x4986]),
            (0x8002, [0x0996, 0x4996]),
        ])

    def test_firewood_stays_on_palette_2(self):
        rows = _decode_bin(BINS / "firewood.bin")
        self.assertEqual(len(rows), 2)
        chars = []
        for header, tiles in rows:
            self.assertEqual(header, 0x8002)
            for word in tiles:
                self.assertEqual(_palette(word), 2)
                chars.append(_char(word))
        # Top on slot 6, bottom on slot 5. Do not collapse them onto one sheet.
        self.assertEqual(chars, [0x1A0, 0x1A1, 0x17E, 0x17F])

    def test_kettle_words_use_palette_3_sheet_07_chars(self):
        rows = _decode_bin(BINS / "timber_kettle.bin")
        words = [w for _, tiles in rows for w in tiles]
        self.assertEqual(words, [0x0CC1, 0x0CCC, 0x0CCD, 0x0CCE])
        for word in words:
            self.assertEqual(_palette(word), 3)
            self.assertTrue(0xC0 <= _char(word) <= 0xFF)


class DungeonBgSheetInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads(SHEETS.read_text())

    def test_audited_sheet_set(self):
        self.assertEqual(self.spec["schema_version"], 1)
        self.assertEqual(self.spec["start"], "0x5D8000")
        self.assertEqual(self.spec["capacity"], 8192)
        ids = [entry["global_sheet"] for entry in self.spec["sheets"]]
        self.assertEqual(ids, ["0x07", "0x1F", "0x22"])
        for entry in self.spec["sheets"]:
            self.assertRegex(entry["base_sha256"], r"^[0-9a-f]{64}$")

    def test_patches_do_not_share_tiles(self):
        seen = set()
        names = set()
        declared = {entry["global_sheet"] for entry in self.spec["sheets"]}
        for patch in self.spec["patches"]:
            self.assertNotIn(patch["name"], names)
            names.add(patch["name"])
            self.assertIn(patch["sheet"], declared)
            if patch["kind"] == "grid_16x16":
                tiles = patch["tiles"]
            elif patch["kind"] == "base_tile_copy":
                tiles = patch["tiles"]
            elif patch["kind"] == "tile_8x8":
                tiles = [patch["tile"]]
            else:
                self.fail(f"unknown patch kind {patch['kind']}")
            for tile in tiles:
                key = (patch["sheet"], tile)
                self.assertNotIn(key, seen, key)
                seen.add(key)

    def test_kettle_patch_matches_tile_words(self):
        kettle = next(p for p in self.spec["patches"] if p["name"] == "timber_kettle")
        self.assertEqual(kettle["kind"], "grid_16x16")
        self.assertEqual(kettle["sheet"], "0x07")
        self.assertEqual(kettle["tiles"], ["0x01", "0x0C", "0x0D", "0x0E"])
        self.assertTrue(kettle["require_blank"])
        source = SHEETS.parent / kettle["source"]
        self.assertTrue(source.is_file())


if __name__ == "__main__":
    unittest.main()
