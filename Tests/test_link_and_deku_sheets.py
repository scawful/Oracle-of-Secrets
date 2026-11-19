#!/usr/bin/env python3
"""Regression & pixel-invariant tests for Human Minish Cap Link & Deku Link sheets."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
GEN_DIR = str(ROOT / "Scripts/Generate")
if GEN_DIR not in sys.path:
    sys.path.insert(0, GEN_DIR)

import build_mc_link_sheet as mc_builder  # noqa: E402
import build_deku_link_sheet as deku_builder  # noqa: E402

MC_SHEET_PATH = ROOT / "Data/graphics/link/mc_link_sheet.4bpp"
DEKU_SHEET_PATH = ROOT / "Masks/gfx/deku_link.bin"
YAZE_BASE_ROM = Path.home() / "Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj/rom"
VANILLA_ALTTP_ROM = Path.home() / "src/hobby/roms/Legend of Zelda, The - A Link to the Past (USA).sfc"

# Lavender slash/swoosh FX cells that legitimately remain identical to vanilla ALTTP
MC_VANILLA_FX_CELLS = {
    (8, 3), (8, 4), (8, 5), (8, 6), (8, 7),
    (9, 0), (9, 1), (9, 2),
    (11, 0),
}

# Upgraded Human MC Link head cells (formerly vanilla blue headband / legacy heads)
MC_UPGRADED_HEADS = {
    (4, 7), (6, 5), (6, 6), (10, 0), (10, 5), (10, 7),
    (23, 1), (25, 5), (26, 1), (26, 4),
}


def cell_pixels(grid: list[list[int]], r: int, c: int) -> list[list[int]]:
    return [grid[r * 16 + y][c * 16 : c * 16 + 16] for y in range(16)]


def color_counts(cell: list[list[int]]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for row in cell:
        for val in row:
            counts[val] = counts.get(val, 0) + 1
    return counts


class MinishCapLinkSheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = MC_SHEET_PATH.read_bytes()
        cls.grid = mc_builder.decode_4bpp_sheet(cls.raw)

    def test_exact_size_and_idempotent_reproducibility(self) -> None:
        self.assertEqual(len(self.raw), mc_builder.SHEET_SIZE)
        # Rebuilding from itself must be byte-exact (CI-safe without external ROM)
        rebuilt_self = mc_builder.build_sheet(self.raw)
        self.assertEqual(rebuilt_self, self.raw)
        # If authoring base ROM is present locally, rebuilding from $108000 must match byte-exact
        if YAZE_BASE_ROM.is_file():
            base = mc_builder.load_base_sheet(YAZE_BASE_ROM)
            self.assertEqual(mc_builder.build_sheet(base), self.raw)
            # And scawful's existing MC heads/walk frames must be preserved verbatim
            base_grid = mc_builder.decode_4bpp_sheet(base)
            for r, c in [
                (0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6), (0, 7),
                (1, 0), (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7),
                (2, 0), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6),
                (3, 0), (3, 1), (3, 2), (3, 3), (3, 4),
            ]:
                self.assertEqual(
                    cell_pixels(self.grid, r, c),
                    cell_pixels(base_grid, r, c),
                    f"Existing scawful cell R{r:02d}C{c} must be preserved untouched",
                )

    def test_zero_leftover_vanilla_alttp_body_or_head_cells(self) -> None:
        if not VANILLA_ALTTP_ROM.is_file():
            self.skipTest("Canonical vanilla ALTTP ROM not present locally")
        van_grid = mc_builder.decode_4bpp_sheet(mc_builder.load_base_sheet(VANILLA_ALTTP_ROM))
        leftover = []
        for r in range(28):
            for c in range(8):
                cell = cell_pixels(self.grid, r, c)
                if not any(v for row in cell for v in row):
                    continue
                if cell == cell_pixels(van_grid, r, c) and (r, c) not in MC_VANILLA_FX_CELLS:
                    leftover.append(f"R{r:02d}C{c}")
        self.assertEqual(leftover, [], f"Leftover untouched vanilla ALTTP cells: {leftover}")

    def test_action_rows_have_green_mail_sleeves_and_no_alttp_yellow_hem(self) -> None:
        # Check every upgraded body cell in R14..R27 and early action rows
        body_cells = [
            (r, c) for (r, c) in mc_builder.CELLS
            if (r, c) not in MC_UPGRADED_HEADS
            and (r, c) not in {(17, 1), (18, 1), (19, 1)}  # combined shocked head+body
        ]
        self.assertGreaterEqual(len(body_cells), 55)
        for r, c in body_cells:
            cell = cell_pixels(self.grid, r, c)
            cnt = color_counts(cell)
            # Must use Mail-recolored tunic/sleeve colors (C10/C11/C12)
            tunic_px = cnt.get(10, 0) + cnt.get(11, 0) + cnt.get(12, 0)
            self.assertGreaterEqual(tunic_px, 16, f"R{r:02d}C{c} lacks mail-recolored tunic/sleeves")
            # No wide ALTTP bright yellow tunic hem (C02 <= 4px for tiny belt buckle only)
            self.assertLessEqual(cnt.get(2, 0), 4, f"R{r:02d}C{c} still has wide ALTTP yellow hem ({cnt.get(2, 0)}px)")
            # No vanilla brown sleeve highlight (C13 == 0 on upgraded pure body cells except R18C5/6 skin crease)
            if (r, c) not in {(18, 5), (18, 6)}:
                self.assertEqual(cnt.get(13, 0), 0, f"R{r:02d}C{c} has leftover C13 brown sleeve pixels")
            # Upper shoulder region must NOT have wide brown sleeve blocks (C14 <= 2)
            # (R13C0 is stored upside-down for V-flipped somersault, so its arms live at y >= 8)
            arm_rows = range(8, 16) if (r, c) == (13, 0) else range(7)
            upper_c14 = sum(1 for y in arm_rows for x in range(16) if cell[y][x] == 14)
            self.assertLessEqual(upper_c14, 2, f"R{r:02d}C{c} has upper-shoulder brown sleeve pixels ({upper_c14})")
            # Zero pink-hair C15 in body cells
            self.assertEqual(cnt.get(15, 0), 0, f"R{r:02d}C{c} contains stray C15 pixel")

    def test_upgraded_heads_have_zero_pink_hair_and_zero_blue_headband(self) -> None:
        for r, c in sorted(MC_UPGRADED_HEADS | {(17, 1), (19, 1)}):
            cell = cell_pixels(self.grid, r, c)
            cnt = color_counts(cell)
            # Zero pink hair (C15)
            self.assertEqual(cnt.get(15, 0), 0, f"Head R{r:02d}C{c} has pink hair C15")
            # Blue (C08) is ONLY for Minish Cap eyes (<= 4px, NEVER a wide 6-14px vanilla headband!)
            self.assertLessEqual(cnt.get(8, 0), 4, f"Head R{r:02d}C{c} has legacy blue headband ({cnt.get(8, 0)}px C08)")

    def test_asm_patch_and_include_wired(self) -> None:
        patch_asm = (ROOT / "Core/link_sheet_patch.asm").read_text(encoding="utf-8")
        main_asm = (ROOT / "Oracle_main.asm").read_text(encoding="utf-8")
        self.assertIn("org $108000", patch_asm)
        self.assertIn('incbin "Data/graphics/link/mc_link_sheet.4bpp"', patch_asm)
        self.assertIn("assert pc() == $10F000", patch_asm)
        self.assertIn('incsrc "Core/link_sheet_patch.asm"', main_asm)


class DekuLinkSheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = DEKU_SHEET_PATH.read_bytes()
        cls.grid = deku_builder.decode_4bpp_sheet(cls.raw)

    def test_exact_size_idempotency_and_no_index_15(self) -> None:
        self.assertEqual(len(self.raw), deku_builder.SHEET_SIZE)
        self.assertEqual(deku_builder.polish_deku_sheet(self.raw), self.raw)
        c15 = sum(1 for row in self.grid for v in row if v == 15)
        self.assertEqual(c15, 0, "Deku sheet must never use undefined color index 15")

    def test_zero_leftover_human_green_tunic_yellow_belt_in_action_rows(self) -> None:
        # All unified Deku body cells across R01..R27 (excluding the 3 mini Deku heads)
        mini_heads = {(25, 5), (26, 1), (26, 4)}
        body_cells = [rc for rc in deku_builder.CELLS if rc not in mini_heads and rc != (10, 0)]
        self.assertGreaterEqual(len(body_cells), 135)
        for r, c in body_cells:
            cell = cell_pixels(self.grid, r, c)
            cnt = color_counts(cell)
            # Zero bright yellow ALTTP belt/tunic band (C06 == 0 in every Deku body cell!)
            self.assertEqual(cnt.get(6, 0), 0, f"Deku body R{r:02d}C{c} still has C06 yellow belt pixels")
            # Zero red clown mittens / red shoes (C09 == 0, C10 == 0)
            self.assertEqual(cnt.get(9, 0) + cnt.get(10, 0), 0, f"Deku body R{r:02d}C{c} has stray red pixels")
            # Must combine warm sculpted wooden bark {2, 5, 7} AND lush green leaf skirt {1, 3, 4, 14}
            bark_px = cnt.get(2, 0) + cnt.get(5, 0) + cnt.get(7, 0)
            leaf_px = cnt.get(1, 0) + cnt.get(3, 0) + cnt.get(4, 0) + cnt.get(14, 0)
            self.assertGreaterEqual(bark_px, 14, f"Deku body R{r:02d}C{c} lacks wooden bark ({bark_px}px)")
            self.assertGreaterEqual(leaf_px, 12, f"Deku body R{r:02d}C{c} lacks green leaf skirt ({leaf_px}px)")
            # Specifically verify R14..R24 action rows are no longer human green-tunic dominated
            if 14 <= r <= 24:
                self.assertGreaterEqual(
                    bark_px / max(1, bark_px + leaf_px),
                    0.35,
                    f"Deku action cell R{r:02d}C{c} looks human green-tunic dominated (bark={bark_px}, leaf={leaf_px})",
                )

    def test_scawful_deku_heads_preserved_with_glowing_eyes_and_leaf_caps(self) -> None:
        # Key Deku front/side head cells must still have glowing yellow eyes (C06) + green cap + bark face
        for r, c in [(0, 0), (0, 1), (0, 3), (0, 4), (0, 5), (0, 7), (1, 7), (20, 0), (20, 1)]:
            cnt = color_counts(cell_pixels(self.grid, r, c))
            self.assertGreaterEqual(cnt.get(6, 0), 10, f"Deku head R{r:02d}C{c} lost yellow eyes/tuft")
            self.assertGreaterEqual(cnt.get(4, 0) + cnt.get(3, 0), 15, f"Deku head R{r:02d}C{c} lost green cap")
            self.assertGreaterEqual(cnt.get(5, 0) + cnt.get(2, 0), 20, f"Deku head R{r:02d}C{c} lost bark face")


if __name__ == "__main__":
    unittest.main()
