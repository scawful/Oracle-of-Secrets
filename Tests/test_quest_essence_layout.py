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
PENDANT_POS = [(15, 17), (13, 19), (15, 21)]  # triangle in the ring centre


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
        draw = DRAW.read_text()
        # Default build has the four-page menu: Pearl and hearts on the top row
        # (!QuestRow's first definition) and the six songs on the bottom row.
        qy, qx = map(int, re.search(r"!QuestRow = menu_offset\((\d+),(\d+)\)", draw).groups())
        row_arg = r"#!QuestRow\+menu_offset\((\d+),\s*(\d+)\)"
        # v4: the area name heads the Map page; Quest draws no location text.
        self.assertNotIn("DrawLocationName", block(quest, "Menu_Quest_Draw"))
        gear = block(quest, "Menu_Quest_Gear")
        self.assertNotIn(".gear_label", gear)
        # Pearl column: first (four-page menu) definition; Menu v5 removes the
        # redundant numeric heart-piece digit under the visual heart container.
        self.assertRegex(gear, r"LDX\.w #!QuestRow\+!QuestPearlCol\s*\n\s*LDY\.w #MoonPearlGFX")
        y, x = re.search(r"!QuestPearlCol = menu_offset\((\d+),(\d+)\)", quest).groups()
        item("moon pearl", qy + int(y), qx + int(x))
        self.assertNotIn("JSR Menu_Quest_Number3", block(quest, "Menu_Quest_Draw"))
        # Gear block: four passive icons (DrawMenuItem offsets).
        names = ["shield", "glove", "boots", "flippers"]
        for name, (y, x) in zip(names, re.findall(r"menu_offset\((\d+),(\d+)\)", between(gear, ".gear_pos", ".gear_gfx"))):
            item(name, int(y), int(x))
        self.assertRegex(gear, r"\.gear_gfx\s*\n\s*dw ShieldGFX,PowerGloveGFX,PegasusBootsGFX,FlippersGFX")
        y, x = re.search(r"!QuestHeart = \$1000\+!QuestRow\+menu_offset\((\d+),(\d+)\)", draw).groups()
        cells["heart piece"] = square(to_cell(self.offset(qy + int(y), qx + int(x))))
        # Four-page menu: the dungeon row is drawn on the Map page, not here.
        self.assertNotIn("Menu_DrawBigKey", block(quest, "Menu_Quest_Draw"))
        notes = block(draw, "Menu_DrawMusicNotes").split(".positions", 1)[1]
        songs = re.findall(r"menu_offset\((\d+),(\d+)\)", notes)
        self.assertEqual(len(songs), 6, "six song notes")
        for index, (y, x) in enumerate(songs):
            item(f"song {index + 1}", int(y), int(x))
        row, col = to_cell(0x1692 - TILEMAP)
        cells["footer (cleared)"] = {(row, col + i) for i in range(0x1C // 2 + 1)}
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
        others = self.other_content()
        for name, cells in others.items():
            if name == "footer (cleared)":
                continue
            for row, col in cells:
                self.assertEqual(self.frame[row * 32 + col], PANEL_BLANK, f"{name} leaves panel at {(row, col)}")
        everything = dict(icons, **others)
        names = list(everything)
        for i, first in enumerate(names):
            for second in names[i + 1:]:
                shared = everything[first] & everything[second]
                self.assertFalse(shared, f"{first} overlaps {second} at {sorted(shared)}")

    def test_left_column_gear_box_and_songs_on_bottom_row(self):
        """2x2 passive gear block shifted down 1 row (rows 11..15), Moon Pearl and
        hearts below it (rows 17..18), leaving row 19 clear above row 21 songs'
        4x4 C4 cursor (top border row 20)."""
        content = self.other_content()
        gear = [cell for n in ("shield", "glove", "boots", "flippers") for cell in content[n]]
        right = max(c for _, c in gear)
        gear_bottom = max(r for r, _ in gear)
        self.assertEqual(min(r for r, _ in gear), 11, "gear top row shifted down 1 row")
        self.assertEqual(gear_bottom, 15, "2x2 gear ends at row 15")
        icons = [min(content[n]) for n in ("shield", "glove", "boots", "flippers")]
        self.assertEqual(icons[0][0], icons[1][0]); self.assertEqual(icons[2][0], icons[3][0])
        self.assertEqual(icons[0][1], icons[2][1]); self.assertEqual(icons[1][1], icons[3][1])
        pearl, heart = min(content["moon pearl"]), min(content["heart piece"])
        self.assertEqual({pearl[0], heart[0]}, {17}, "pearl and hearts sit at rows 17..18")
        self.assertGreater(min(pearl[0], heart[0]), gear_bottom + 1, "blank separator row below gear")
        self.assertLess(max(r for r, _ in content["moon pearl"] | content["heart piece"]), 19,
                        "row 19 stays completely clear above row 21 songs 4x4 cursor (top border row 20)")
        self.assertLess(pearl[1], heart[1])
        ring_left = min(c for _, c in self.crystal_cells())
        self.assertLess(right, ring_left, "gear left of the essence ring")
        self.assertLess(max(c for _, c in content["heart piece"]), ring_left)
        songs = [min(content[f"song {i}"]) for i in range(1, 7)]
        self.assertEqual({row for row, _ in songs}, {21})
        self.assertEqual([c for _, c in songs], sorted(c for _, c in songs), "songs run left to right")
        ring_bottom = max(row for row, _ in self.crystal_cells()) + 1
        self.assertGreater(21, ring_bottom, "songs sit below the essence ring")

    def test_map_page_dungeon_row(self):
        """Map & Spoils page: Map cell (15,15) alongside hoverable dungeon icons
        (ChestKey, BigKey, Chest at (15, 18/21/24)) below the right-hand 2-line
        Area Name (rows 11..12, cols 15..26), clear of the mini-map, divider, and footer."""
        draw = DRAW.read_text()
        page = (ROOT / "Menu" / "menu_map_travel.asm").read_text()
        body = block(page, "MenuMapTravel_Draw")
        self.assertIn("JSR Menu_DrawBigKey", body)
        self.assertIn("JSR Menu_DrawBigChestKey", body)
        item_base = self.draw_menu_item_base()
        dy, dx = map(int, re.search(r"!DungeonRow = menu_offset\((\d+),(\d+)\)", draw).groups())
        found = re.findall(r"LDX\.w #!DungeonRow\+menu_offset\((\d+),\s*(\d+)\) ; Map & Spoils page", draw)
        self.assertEqual(len(found), 3, "chest key, big key, treasure")
        icons = [to_cell(self.offset(dy + int(y), dx + int(x)) + item_base) for y, x in found]
        self.assertEqual({row for row, _ in icons}, {15})
        self.assertEqual(sorted(col for _, col in icons), [18, 21, 24])
        cy, cx = map(int, re.search(r"!MapCellPos = menu_offset\((\d+),(\d+)\)", page).groups())
        cell = to_cell(self.offset(cy, cx) + item_base)
        self.assertEqual(cell, (15, 15))
        # Fixed regions: Map icon 2x2, 2-line area name (11..12, 15..26), mini-map, divider, footer
        taken = square(cell)
        taken |= {(r, c) for r in (11, 12) for c in range(15, 27)}
        taken |= {(r, c) for r in range(11, 19) for c in range(6, 14)}  # 8x8 mini-map
        taken |= {(19, c) for c in range(6, 26)}  # horizontal divider
        row, col = to_cell(0x1692 - TILEMAP)
        taken |= {(row, col + i) for i in range(0x1C // 2 + 1)}
        cells = set()
        for origin in icons:
            for c in square(origin):
                self.assertEqual(self.frame[c[0] * 32 + c[1]], PANEL_BLANK, f"dungeon icon leaves panel at {c}")
            self.assertFalse(square(origin) & cells, "dungeon icons overlap")
            cells |= square(origin)
        self.assertFalse(cells & taken, f"dungeon row overlaps {sorted(cells & taken)}")

    def test_essences_keep_one_tile_gap(self):
        essences = [square(cell) for cell in self.crystal_cells()]
        icons = essences + [square(to_cell(self.offset(*p))) for p in self.pendant_helper]
        # Essences keep a full one-tile gap from each other. The tight ring
        # (Quest Q2) lets a pendant meet an essence corner-to-corner only.
        for i, first in enumerate(essences):
            halo = {(r + dr, c + dc) for r, c in first for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
            edge = {(r + dr, c + dc) for r, c in first for dr, dc in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))}
            for j, second in enumerate(icons):
                if i != j:
                    near = halo if j < len(essences) else edge
                    self.assertFalse(near & second, f"D{i + 1} touches icon {j}")

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
