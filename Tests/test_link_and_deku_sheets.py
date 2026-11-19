#!/usr/bin/env python3
"""Regression & pixel-invariant tests for Human Minish Cap Link & Deku Link sheets."""
from __future__ import annotations

from pathlib import Path
import subprocess
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
        cls.zgrid = mc_builder.decode_4bpp_sheet(mc_builder.load_zspr_gfx(mc_builder.DEFAULT_ZSPR))

    def test_exact_size_and_reproducibility(self) -> None:
        self.assertEqual(len(self.raw), mc_builder.SHEET_SIZE)
        # Rebuilding from itself must be byte-exact (CI-safe without external ROM)
        self.assertEqual(mc_builder.build_sheet(self.raw), self.raw)
        if YAZE_BASE_ROM.is_file():
            base = mc_builder.load_base_sheet(YAZE_BASE_ROM)
            self.assertEqual(mc_builder.build_sheet(base), self.raw)
            base_grid = mc_builder.decode_4bpp_sheet(base)
            # scawful's existing MC heads/walk frames must be preserved verbatim
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

    def test_praying_pull_flute_bed_match_remapped_inthebeef_zspr(self) -> None:
        # Praying (R17C1/R18C1/R19C1), Upside-Down (R04C7), Flute (R25C5), Bed (R26C1/C4)
        for r, c in mc_builder.ZSPR_HEAD_CELLS:
            got = cell_pixels(self.grid, r, c)
            exp = [[mc_builder.ZSPR_TO_ROM_PAL[v] for v in row] for row in cell_pixels(self.zgrid, r, c)]
            self.assertEqual(got, exp, f"Head cell R{r:02d}C{c} must match remapped InTheBEEF ZSPR")
            cnt = color_counts(got)
            self.assertEqual(cnt.get(15, 0), 0, f"Head R{r:02d}C{c} has pink hair C15")
            self.assertLessEqual(cnt.get(8, 0), 4, f"Head R{r:02d}C{c} has blue headband")

        # Midway pull (R13C0) and all secondary ZSPR body frames
        for r, c in mc_builder.ZSPR_BODY_CELLS:
            got = cell_pixels(self.grid, r, c)
            exp = [[mc_builder.ZSPR_TO_ROM_BODY[v] for v in row] for row in cell_pixels(self.zgrid, r, c)]
            self.assertEqual(got, exp, f"Body cell R{r:02d}C{c} must match remapped InTheBEEF ZSPR")
            cnt = color_counts(got)
            self.assertEqual(cnt.get(15, 0), 0, f"Body R{r:02d}C{c} has stray C15")

    def test_no_inthebeef_signature_cells_imported(self) -> None:
        # Unused ZSPR Easter-egg blocks must NEVER be in ZSPR_HEAD_CELLS or ZSPR_BODY_CELLS
        sig_cells = {
            (16, 2), (16, 3), (16, 4), (17, 3), (17, 4), (17, 5),
            (21, 7), (22, 0), (22, 1), (22, 2), (22, 3), (22, 4), (22, 5), (22, 6), (22, 7), (23, 0),
        }
        imported = set(mc_builder.ZSPR_HEAD_CELLS) | set(mc_builder.ZSPR_BODY_CELLS)
        self.assertTrue(imported.isdisjoint(sig_cells), f"Signature cells leaked: {imported & sig_cells}")

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
        cls.orig = subprocess.check_output(
            ["git", "-C", str(ROOT), "show", f"{deku_builder.ORIG_GIT_REV}:Masks/gfx/deku_link.bin"]
        )
        cls.orig_grid = deku_builder.decode_4bpp_sheet(cls.orig)

    def test_exact_size_reproducibility_and_no_index_15(self) -> None:
        self.assertEqual(len(self.raw), deku_builder.SHEET_SIZE)
        self.assertEqual(deku_builder.build_sheet(self.orig), self.raw)
        c15 = sum(1 for row in self.grid for v in row if v == 15)
        self.assertEqual(c15, 0, "Deku sheet must never use undefined color index 15")

    def test_original_slim_body_and_cute_red_gloves_boots_preserved(self) -> None:
        # ALL of R00..R13 must be 100% byte-for-byte identical to original slim Deku Link!
        self.assertEqual(self.raw[: 14 * 8 * 128], self.orig[: 14 * 8 * 128])
        # Verify red gloves/boots (C09/C10) are intact on core walk/idle cells (R01..R03, R12..R13)
        red_px = sum(
            1
            for r in (1, 2, 3, 12, 13)
            for c in range(8)
            for row in cell_pixels(self.grid, r, c)
            for v in row
            if v in (9, 10)
        )
        self.assertGreaterEqual(red_px, 400, f"Cute red gloves/boots were stripped ({red_px}px)")

    def test_surgical_recolor_preserves_exact_silhouette_and_removes_yellow_belt(self) -> None:
        for r, c in deku_builder.VANILLA_TUNIC_CELLS:
            got = cell_pixels(self.grid, r, c)
            ref = cell_pixels(self.orig_grid, r, c)
            # Zero fattening: exact same opaque pixel mask on every recolored cell!
            got_mask = [[v != 0 for v in row] for row in got]
            ref_mask = [[v != 0 for v in row] for row in ref]
            self.assertEqual(got_mask, ref_mask, f"Deku cell R{r:02d}C{c} silhouette changed (fattened!)")
            # Zero leftover bright yellow human belt (C06)
            cnt = color_counts(got)
            self.assertEqual(cnt.get(6, 0), 0, f"Deku cell R{r:02d}C{c} still has C06 yellow belt")


if __name__ == "__main__":
    unittest.main()
