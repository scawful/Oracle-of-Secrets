#!/usr/bin/env python3
"""Eon Abyss Mode 7 world map: hardware limits, parity, determinism, and 457d8fcb marker alignment."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Scripts" / "Generate"))

import build_abyss_world_map as builder  # noqa: E402

WM = ROOT / "Overworld" / "world_map"
ASM = ROOT / "Overworld" / "world_map.asm"


def _unpack_quadrants(tileset: bytes) -> list[list[int]]:
    grid = [[0] * 64 for _ in range(64)]
    quads = ((0, 0), (0, 32), (32, 0), (32, 32))
    for quad, (row0, col0) in enumerate(quads):
        base = quad * 1024
        for row in range(32):
            for col in range(32):
                grid[row0 + row][col0 + col] = tileset[base + row * 32 + col]
    return grid


def _parse_asm_marker(asm_text: str, label: str) -> tuple[int, int]:
    match = re.search(rf"{re.escape(label)}:\s*\{{(.*?)\n\}}", asm_text, re.DOTALL)
    if not match:
        raise AssertionError(f"Missing ASM marker block {label}")
    body = match.group(1)

    def _byte(addr: str) -> int:
        m = re.search(rf"LDA\.b\s+#\$([0-9A-Fa-f]{{2}})\s*:\s*STA\.l\s+\${addr}", body)
        if not m:
            raise AssertionError(f"Missing write to ${addr} in {label}")
        return int(m.group(1), 16)

    wx = (_byte("7EC10B") << 8) | _byte("7EC10A")
    wy = (_byte("7EC109") << 8) | _byte("7EC108")
    return wx, wy


def _sample_mode7_pixel(tileset: bytes, gfx: bytes, full_x: int, full_y: int) -> int:
    grid = _unpack_quadrants(tileset)
    tile = grid[full_y // 8][full_x // 8]
    return gfx[tile * 64 + (full_y % 8) * 8 + (full_x % 8)]


class AbyssWorldMapTest(unittest.TestCase):
    def test_checked_in_bins_match_generator(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "Scripts/Generate/build_abyss_world_map.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_exact_file_sizes_and_hardware_limits(self) -> None:
        tileset = (WM / "DwMapTileset.bin").read_bytes()
        gfx = (WM / "DwMapGfx.bin").read_bytes()
        palette = (WM / "dw_palette.bin").read_bytes()

        self.assertEqual(len(tileset), 4096)
        self.assertEqual(len(gfx), 16384)
        self.assertEqual(len(palette), 256)

        # All Mode 7 CHR indices stay strictly in CGRAM BG range 0..127.
        self.assertTrue(all(px < 128 for px in gfx))

        used = set(tileset)
        for frame_tile in builder.VANILLA_FRAME_TILES:
            self.assertIn(frame_tile, used)
        content = used - builder.RESERVED_TILES
        self.assertLessEqual(len(content), builder.MAX_CONTENT_TILES)
        self.assertGreater(len(content), 100)

        # Every used tile pixel is non-zero (index 0 is Mode 7 backdrop).
        for tile_idx in used:
            tile_pixels = gfx[tile_idx * 64:(tile_idx + 1) * 64]
            self.assertTrue(all(1 <= px < 128 for px in tile_pixels), f"tile ${tile_idx:02X} uses index 0")

        # Tile $EF matches solid parchment fill for WorldMap_FillTilemapWithEF ($0ABDA5).
        self.assertEqual(
            gfx[builder.BORDER_FILL_EF * 64:(builder.BORDER_FILL_EF + 1) * 64],
            bytes([builder.PARCH_BASE] * 64),
        )

    def test_outer_parchment_frame_matches_lw_and_sw(self) -> None:
        dw_grid = _unpack_quadrants((WM / "DwMapTileset.bin").read_bytes())
        lw_grid = _unpack_quadrants((WM / "LwMapTileset.bin").read_bytes())
        sw_grid = _unpack_quadrants((WM / "SwMapTileset.bin").read_bytes())
        dw_pal = (WM / "dw_palette.bin").read_bytes()

        for row in range(64):
            for col in range(64):
                if 16 <= row < 48 and 16 <= col < 48:
                    self.assertNotIn(dw_grid[row][col], builder.RESERVED_TILES, (row, col))
                else:
                    self.assertEqual(dw_grid[row][col], lw_grid[row][col], (row, col))
                    self.assertEqual(dw_grid[row][col], sw_grid[row][col], (row, col))

        # Parchment BGR555 words match vanilla Lw/Sw border table colors exactly.
        for idx, want_word in builder.EXACT_BGR555.items():
            got_word = dw_pal[idx * 2] | (dw_pal[idx * 2 + 1] << 8)
            self.assertEqual(got_word, want_word, f"palette index {idx}")

    def test_generator_is_deterministic(self) -> None:
        self.assertEqual(builder.build_assets(), builder.build_assets())

    def test_preview_cli_writes_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_png = Path(tmp) / "preview.png"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "Scripts/Generate/build_abyss_world_map.py"),
                    "--check",
                    "--preview",
                    str(out_png),
                    "--scale",
                    "1",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(out_png.is_file())
            self.assertEqual(out_png.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_story_markers_and_landmark_alignment(self) -> None:
        text = ASM.read_text()
        for label in ("DrawPowerPendant", "DrawWisdomPendant", "DrawCouragePendant"):
            self.assertNotIn(label, text)

        asm_markers = {
            "sword": _parse_asm_marker(text, "DrawMasterSwordIcon"),
            "shield": _parse_asm_marker(text, "DrawForestShieldIcon"),
            "fortress": _parse_asm_marker(text, "DrawFortressOfSecretsIcon"),
            "pyramid": _parse_asm_marker(text, "DrawFinalBossIcon"),
            "escape": _parse_asm_marker(text, "DrawEonEscapeIcon"),
        }
        self.assertEqual(asm_markers, builder.MARKERS_WORLD)

        tileset = (WM / "DwMapTileset.bin").read_bytes()
        gfx = (WM / "DwMapGfx.bin").read_bytes()
        grid = _unpack_quadrants(tileset)

        expected_palette_sets = {
            # Sword glade: golden pedestal / cream clearing
            "sword": {builder.GOLD_HI, builder.GOLD_MID, builder.CREAM, builder.SAND_HI},
            # Shield sanctuary: mystic crystal dais / sunlit glade
            "shield": {builder.MYSTIC_HI, builder.SLATE_HI, builder.PATH_HI, builder.GRASS_HI},
            # Fortress North Gate: dark arched doorway framed by gold/stone gateposts
            "fortress": {builder.INK_DARK, builder.FORT_WALL, builder.GOLD_HI, builder.GOLD_MID},
            # Final Boss Pit: dark volcanic caldera mouth rimmed with lava crust
            "pyramid": {builder.INK_DARK, builder.LAVA_CRUST, builder.VOLC_DARK, builder.LAVA_BRIGHT},
            # Eon Escape glade: sunlit clearing center
            "escape": {builder.CREAM, builder.PATH_HI, builder.GRASS_HI},
        }
        ocean_colors = {builder.SEA_ABYSS, builder.SEA_DEEP, builder.SEA_MID, builder.SEA_SHALLOW, builder.SEA_FOAM}

        for name, (wx, wy) in asm_markers.items():
            full_x = 128 + (wx >> 4)
            full_y = 128 + (wy >> 4)
            tx, ty = full_x // 8, full_y // 8
            self.assertTrue(16 <= tx < 48 and 16 <= ty < 48, f"{name} outside central Mode 7 map")
            self.assertNotIn(grid[ty][tx], builder.RESERVED_TILES, name)
            px_color = _sample_mode7_pixel(tileset, gfx, full_x, full_y)
            self.assertNotIn(px_color, ocean_colors, f"{name} landed on ocean")
            self.assertIn(
                px_color,
                expected_palette_sets[name],
                f"{name} at ({full_x},{full_y}) hit unexpected palette index {px_color}",
            )


if __name__ == "__main__":
    unittest.main()
