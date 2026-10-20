"""Static Quest page essence layout contract; reads source only, no assembler or emulator.

Models Menu_Quest_Progress as written in Menu/menu_quest.asm: the essence bit
table, loop bound, 2x2 footprint and positions, then places every other Quest
page writer on the 32x32 tilemap buffer at $1000 to prove no overlap.
"""
import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEST = ROOT / "Menu" / "menu_quest.asm"
DRAW = ROOT / "Menu" / "menu_draw.asm"
SYMBOLS = ROOT / "Core" / "symbols.asm"
SRAM = ROOT / "Core" / "sram.asm"
FRAME = ROOT / "Menu" / "tilemaps" / "menu_frame.tilemap"

TILEMAP = 0x1000
PANEL_BLANK = 0x3417
SKY_BIT = 0x80  # contract value of !Crystal_D8_Sky supplied by the progression worker

ORDER = [
    "!Crystal_D1_MushroomGrotto", "!Crystal_D2_TailPalace", "!Crystal_D3_KalyxoCastle",
    "!Crystal_D4_ZoraTemple", "!Crystal_D5_GlaciaEstate", "!Crystal_D6_GoronMines",
    "!Crystal_D7_DragonShip", "!Crystal_D8_Sky",
]
LEGACY_BITS = {
    "!Crystal_D1_MushroomGrotto": 0x02, "!Crystal_D2_TailPalace": 0x10,
    "!Crystal_D3_KalyxoCastle": 0x40, "!Crystal_D4_ZoraTemple": 0x20,
    "!Crystal_D5_GlaciaEstate": 0x04, "!Crystal_D6_GoronMines": 0x01,
    "!Crystal_D7_DragonShip": 0x08,
}
PENDANT_POS = [(15, 10), (17, 8), (17, 12)]


def block(text, label):
    match = re.search(rf"^{label}:\s*\n\{{\n(.*?)^\}}", text, re.S | re.M)
    if not match:
        raise AssertionError(f"{label} block not found")
    return match.group(1)


def between(text, start, end):
    match = re.search(rf"^{re.escape(start)}\s*$(.*?)^{re.escape(end)}\s*$", text, re.S | re.M)
    if not match:
        raise AssertionError(f"{start}..{end} section not found")
    return match.group(1)


def menu_offset_function():
    expr = re.search(r"function menu_offset\(y,x\)\s*=\s*(.+)$", SYMBOLS.read_text(), re.M).group(1)
    return lambda y, x: eval(expr, {"__builtins__": {}}, {"y": y, "x": x})


def to_cell(byte_offset):
    if byte_offset % 2:
        raise AssertionError(f"odd tilemap offset {byte_offset:#x}")
    return divmod(byte_offset // 2, 32)


def square(origin):
    row, col = origin
    return {(row, col), (row, col + 1), (row + 1, col), (row + 1, col + 1)}


class QuestEssenceLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.offset = staticmethod(menu_offset_function())
        quest = QUEST.read_text()
        cls.progress = block(quest, "Menu_Quest_Progress")
        cls.draw_text = quest
        cls.essence_loop = between(cls.progress, ".essences", ".pendants")
        cls.bits = re.findall(r"!Crystal_\w+", between(cls.progress, ".crystal_bits", ".crystal_pos"))
        cls.crystal_helper = [(int(y), int(x)) for y, x in re.findall(
            r"menu_offset\((\d+),(\d+)\)", between(cls.progress, ".crystal_pos", ".pendant_bits"))]
        cls.pendant_helper = [(int(y), int(x)) for y, x in re.findall(
            r"menu_offset\((\d+),(\d+)\)", between(cls.progress, ".pendant_pos", ".pendant_tiles"))]
        cls.essence_bound = int(re.search(
            r"CPY\.b #\$([0-9A-F]{2}) : BCC \.essences", cls.progress).group(1), 16)
        cls.pendant_bound = int(re.search(
            r"CPY\.b #\$([0-9A-F]{2}) : BCC \.pendants", cls.progress).group(1), 16)
        cls.owned_tile = int(re.search(r"LDA\.w #\$([0-9A-F]{4}) : BRA \.triangle", cls.essence_loop).group(1), 16)
        cls.empty_tile = int(re.search(r"^\.empty\s*\n\s*LDA\.w #\$([0-9A-F]{4})", cls.essence_loop, re.M).group(1), 16)
        cls.essence_stores = [int(v, 16) - TILEMAP for v in re.findall(r"STA\.w \$([0-9A-F]{4}),X", cls.essence_loop)]
        frame = FRAME.read_bytes()
        cls.frame = [int.from_bytes(frame[i:i + 2], "little") for i in range(0, len(frame), 2)]
        cls.sram = {name: int(value, 16) for name, value in re.findall(
            r"^(!Crystal_\w+)\s*=\s*\$([0-9A-Fa-f]+)", SRAM.read_text(), re.M)}

    def bit_values(self):
        return [self.sram.get(name, SKY_BIT) if name == "!Crystal_D8_Sky" else self.sram[name]
                for name in self.bits]

    def crystal_cells(self):
        return [to_cell(self.offset(y, x)) for y, x in self.crystal_helper]

    def draw_menu_item_base(self):
        body = block(DRAW.read_text(), "DrawMenuItem")
        stores = [int(v, 16) for v in re.findall(r"STA\.w \$([0-9A-F]{4}),X", body)]
        self.assertEqual([s - stores[0] for s in stores], [0x00, 0x02, 0x40, 0x42])
        return stores[0] - TILEMAP

    def other_content(self):
        """Cells written by every other Quest page writer (default equipment-menu build)."""
        item_base = self.draw_menu_item_base()
        cells = {}

        def item(name, y, x):
            cells[name] = square(to_cell(self.offset(y, x) + item_base))

        def run(name, y, x, tiles):
            row, col = to_cell(self.offset(y, x))
            cells[name] = {(row, col + i) for i in range(tiles)}

        quest = self.draw_text
        location = re.search(r"LDX\.w #\$([0-9A-F]{4})\n\.location\n\s*LDA\.w \$12CC,X : "
                             r"STA\.w \$1000\+menu_offset\((\d+),(\d+)\),X", quest)
        run("location label", int(location.group(2)), int(location.group(3)), int(location.group(1), 16) // 2 + 1)
        gear = block(quest, "Menu_Quest_Gear")
        label = re.search(r"LDX\.w #\$([0-9A-F]{4})\n\.gear_label\n\s*LDA\.w \.gear,X : "
                          r"STA\.w \$1000\+menu_offset\((\d+),(\d+)\),X", gear)
        run("GEAR label", int(label.group(2)), int(label.group(3)), int(label.group(1), 16) // 2 + 1)
        gear_pos = re.findall(r"menu_offset\((\d+),(\d+)\)", between(gear, ".pos", ".gfx"))
        self.assertEqual(len(gear_pos), 6)
        for index, (y, x) in enumerate(gear_pos):
            item(f"gear icon {index}", int(y), int(x))
        y, x = re.search(r"LDX\.w #menu_offset\((\d+),(\d+)\)[^\n]*\n\s*LDY\.w #MoonPearlGFX", gear).groups()
        item("moon pearl", int(y), int(x))
        y, x = re.search(r"LDX\.w #menu_offset\((\d+),(\d+)\)\n\s*JSR Menu_Quest_Number3", quest).groups()
        run("heart piece count", int(y), int(x), 3)
        draw = DRAW.read_text()
        y, x = re.search(r"!QuestHeart = \$1000\+menu_offset\((\d+),(\d+)\)", draw).groups()
        cells["heart piece"] = square(to_cell(self.offset(int(y), int(x))))
        dungeon = re.findall(r"if !ENABLE_EQUIPMENT_MENU == 1\n\s*LDX\.w #menu_offset\((\d+),\s*(\d+)\)", draw)
        self.assertEqual(len(dungeon), 4, "big key, treasure, map, big chest key")
        for index, (y, x) in enumerate(dungeon):
            item(f"dungeon item {index}", int(y), int(x))
        row, col = to_cell(0x1692 - TILEMAP)
        cells["footer name/clock"] = {(row, col + i) for i in range(0x1C // 2 + 1)}
        return cells

    def simulate(self, crystals):
        screen = {}
        for slot, (bit, origin) in enumerate(zip(self.bit_values(), self.crystal_helper)):
            if slot >= self.essence_bound:
                break
            tile = self.owned_tile if bit & crystals else self.empty_tile
            for store, value in zip(self.essence_stores, (tile, tile + 1, tile + 0x10, tile + 0x11)):
                row, col = to_cell(self.offset(*origin) + store)
                screen[(row, col)] = (slot, value)
        return screen

    def test_bit_table_preserves_identity_and_display_order(self):
        self.assertEqual(self.bits, ORDER)
        for name, value in LEGACY_BITS.items():
            self.assertEqual(self.sram[name], value, name)
        values = self.bit_values()
        self.assertEqual(values[7], SKY_BIT)
        self.assertEqual(len(set(values)), 8)
        self.assertTrue(all(v and not v & (v - 1) for v in values))
        self.assertEqual(sum(values), 0xFF)

    @unittest.skipUnless("!Crystal_D8_Sky" in SRAM.read_text(), "Core/sram.asm gains !Crystal_D8_Sky on integration")
    def test_core_supplies_sky_bit(self):
        self.assertEqual(self.sram["!Crystal_D8_Sky"], SKY_BIT)

    def test_loop_bounds_match_tables(self):
        self.assertEqual(self.essence_bound, 8)
        self.assertEqual(len(self.bits), self.essence_bound)
        self.assertEqual(len(self.crystal_helper), self.essence_bound)
        self.assertEqual(self.pendant_bound, 3)
        self.assertEqual(self.pendant_helper, PENDANT_POS)
        self.assertEqual(sorted(self.essence_stores), [0x00, 0x02, 0x40, 0x42])

    def test_routine_only_writes_tilemap_and_scratch(self):
        for target in re.findall(r"STA\.[bwl] (\S+?)(?:,[XY])?(?:\s|$)", self.progress):
            value = int(target.lstrip("$"), 16)
            self.assertTrue(value == 0x04 or 0x1000 <= value <= 0x17FF, target)

    def test_owned_state_per_crystal_value(self):
        values = self.bit_values()
        cases = {0x00: set(), SKY_BIT: {7}, 0x7F: set(range(7)), 0xFF: set(range(8))}
        cases.update({bit: {slot} for slot, bit in enumerate(values)})
        for crystals, owned in cases.items():
            with self.subTest(crystals=f"${crystals:02X}"):
                screen = self.simulate(crystals)
                self.assertEqual(len(screen), 32)
                shown = {slot for slot, tile in screen.values() if tile == self.owned_tile}
                self.assertEqual(shown, owned)
                empty = {slot for slot, tile in screen.values() if tile == self.empty_tile}
                self.assertEqual(empty, set(range(8)) - owned)

    def test_footprints_stay_inside_panel_without_overlap(self):
        icons = {f"D{slot + 1}": square(cell) for slot, cell in enumerate(self.crystal_cells())}
        icons.update({f"pendant {i}": square(to_cell(self.offset(*p))) for i, p in enumerate(self.pendant_helper)})
        for name, cells in icons.items():
            for row, col in cells:
                self.assertEqual(self.frame[row * 32 + col], PANEL_BLANK, f"{name} leaves panel at {(row, col)}")
        everything = dict(icons, **self.other_content())
        names = list(everything)
        for i, first in enumerate(names):
            for second in names[i + 1:]:
                shared = everything[first] & everything[second]
                self.assertFalse(shared, f"{first} overlaps {second} at {sorted(shared)}")

    def test_essences_keep_one_tile_gap(self):
        essences = [square(cell) for cell in self.crystal_cells()]
        icons = essences + [square(to_cell(self.offset(*p))) for p in self.pendant_helper]
        for i, first in enumerate(essences):
            halo = {(r + dr, c + dc) for r, c in first for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
            for j, second in enumerate(icons):
                if i != j:
                    self.assertFalse(halo & second, f"D{i + 1} touches icon {j}")

    def test_clockwise_order_and_mirror_balance(self):
        centres = [(row + 1, col + 1) for row, col in self.crystal_cells()]
        pendant_axis = sum(to_cell(self.offset(*p))[1] + 1 for p in self.pendant_helper) / 3
        mid_row = sum(r for r, _ in centres) / 8
        mid_col = sum(c for _, c in centres) / 8
        self.assertEqual(mid_col, pendant_axis)
        angles = [math.atan2(c - mid_col, mid_row - r) % (2 * math.pi) for r, c in centres]
        turns = [(a - angles[0]) % (2 * math.pi) for a in angles]
        self.assertEqual(turns, sorted(turns), "D1..D8 must run clockwise")
        cells = set(self.crystal_cells())
        mirrored = {(row, int(2 * pendant_axis) - col - 2) for row, col in cells}
        self.assertEqual(mirrored, cells)


if __name__ == "__main__":
    unittest.main()
