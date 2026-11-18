#!/usr/bin/env python3
"""Focused unit tests for scene_intent_common, scene_intent_preflight, and donor_formation_audition."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import scene_intent_common as C  # noqa: E402
import scene_intent_preflight as P  # noqa: E402
import donor_formation_audition as D  # noqa: E402


def _make_bgr555_word(r8: int, g8: int, b8: int) -> int:
    return C.rgb_to_bgr555((r8, g8, b8))


def _encode_3bpp_tile8(px: tuple[int, ...]) -> bytes:
    """Encode 64 palette indices (0..7) into 24-byte SNES 3bpp tile."""
    buf = bytearray(24)
    for y in range(8):
        p0 = p1 = p2 = 0
        for x in range(8):
            v = px[y * 8 + x] & 7
            bit = 7 - x
            p0 |= (v & 1) << bit
            p1 |= ((v >> 1) & 1) << bit
            p2 |= ((v >> 2) & 1) << bit
        buf[2 * y] = p0
        buf[2 * y + 1] = p1
        buf[16 + y] = p2
    return bytes(buf)


class SceneIntentToolsTest(unittest.TestCase):
    def test_room_partition_gate_detects_disconnected_subroom(self):
        # Model 64x64 grid: L-shaped Library West+NE + isolated SE Pot Room.
        grid = [[0x01 for _ in range(64)] for _ in range(64)]
        for y in range(11, 59):
            for x in range(5, 27):
                grid[y][x] = 0x00
        # Open doorway + NE Study wing
        for y in range(14, 18):
            for x in range(27, 37):
                grid[y][x] = 0x8E if x == 34 else 0x00
        for y in range(11, 27):
            for x in range(37, 59):
                grid[y][x] = 0x00
        # Disconnected SE sub-room
        for y in range(45, 59):
            for x in range(41, 55):
                grid[y][x] = 0x00

        comps = P.partition_room_grid(grid)
        self.assertEqual(len(comps), 2)
        c_main, c_se = comps[0], comps[1]
        self.assertGreater(c_main["tile_count"], c_se["tile_count"])
        self.assertEqual(c_se["quadrant"], "SE")

        # Entrance E49 enters West Wing; SE has no entrance from E49.
        e49_comp = P.map_point_to_component(comps, 120, 464)
        e4a_comp = P.map_point_to_component(comps, 376, 464)
        self.assertEqual(e49_comp, c_main["component_id"])
        self.assertEqual(e4a_comp, c_se["component_id"])
        self.assertNotEqual(e49_comp, e4a_comp)

    def test_exterior_building_footprint(self):
        # 32x32 OW map on parent 0x00: house tiles around local (10, 6..8).
        grid = [[0 for _ in range(32)] for _ in range(32)]
        for y in range(6, 9):
            for x in range(10, 14):
                grid[y][x] = 1
        tile16s = [(0, 0, 0, 0), (1, 1, 1, 1)]
        tile_types = bytearray(512)
        tile_types[1] = 0x01  # solid wall
        area_rep = {
            "area_id": "0x00",
            "grid_tile16": grid,
            "tile16_table": tile16s,
            "tile_types": bytes(tile_types),
        }
        fp = P.detect_exterior_building_footprint(area_rep, 11 * 16, 8 * 16)
        self.assertTrue(fp["building_found"])
        self.assertEqual((fp["width_tiles"], fp["height_tiles"]), (4, 3))
        self.assertEqual((fp["width_px"], fp["height_px"]), (64, 48))

    def test_perceptual_remap_preserves_bg0_and_matches_hue(self):
        # Index 0 must stay 0 (transparent BG0); warm brown pixels match brown ramp over green ramp.
        src_pal8 = [
            (0, 0, 0),       # 0 = BG0
            (248, 248, 248), # 1 = white highlight
            (216, 144, 72),  # 2 = warm timber tan
            (128, 72, 32),   # 3 = dark bark brown
            (56, 32, 16),
            (240, 200, 140),
            (180, 100, 48),
            (96, 48, 24),
        ]
        # Checker with BG0 border (index 0) and indices 1, 2, 3.
        px = tuple(
            0 if (x == 0 or y == 0) else (1 if (x + y) % 3 == 0 else (2 if x < 4 else 3))
            for y in range(8) for x in range(8)
        )
        green_cand = {
            "row": 2, "high_half": False, "label": "R2:L",
            "pal8": [(0, 0, 0), (32, 120, 32), (24, 96, 24), (16, 72, 16), (48, 160, 48), (64, 192, 64), (16, 56, 16), (80, 224, 80)],
        }
        timber_cand = {
            "row": 3, "high_half": True, "label": "R3:R",
            "pal8": [(0, 0, 0), (240, 240, 240), (210, 140, 68), (124, 68, 28), (48, 24, 12), (224, 184, 120), (168, 96, 40), (88, 40, 16)],
        }
        for c in (green_cand, timber_cand):
            c["labs"] = [C.rgb_to_lab(rgb) for rgb in c["pal8"]]

        rem = D.remap_tile8_perceptual(px, src_pal8, [green_cand, timber_cand])
        self.assertEqual(rem["target_subpal"], "R3:R")
        for s_val, d_val in zip(px, rem["px"]):
            if s_val == 0:
                self.assertEqual(d_val, 0, "BG0 index 0 must never become opaque")
            else:
                self.assertNotEqual(d_val, 0, "Opaque source must never collapse onto BG0")
        self.assertEqual(rem["color_map"][1], 1)
        self.assertEqual(rem["color_map"][2], 2)
        self.assertEqual(rem["color_map"][3], 3)

    def test_perceptual_remap_preserves_contrast_no_flattening(self):
        # Two close bright green shades must stay distinct (never flatten to 1 shade).
        src_pal8 = [(0, 0, 0), (144, 248, 80), (112, 224, 64), (72, 160, 48), (48, 120, 32), (24, 80, 24), (16, 48, 16), (200, 248, 120)]
        px = tuple(1 if (x + y) % 2 == 0 else 2 for y in range(8) for x in range(8))
        cand = {
            "row": 5, "high_half": False, "label": "R5:L",
            "pal8": [(0, 0, 0), (32, 200, 40), (24, 152, 32), (16, 104, 24), (120, 80, 40), (90, 60, 30), (60, 40, 20), (220, 220, 200)],
        }
        cand["labs"] = [C.rgb_to_lab(rgb) for rgb in cand["pal8"]]
        rem = D.remap_tile8_perceptual(px, src_pal8, [cand])
        self.assertNotEqual(rem["color_map"][1], rem["color_map"][2])
        self.assertIsNotNone(C.canonical_tile8(rem["px"], preserve_zero=True))

    def test_marginal_tile8_cost_with_hv_flips_and_dedupe(self):
        # Build 3 synthetic Tile8s: ch0 (in target), ch1 (in vanilla), ch2 (genuinely new asymmetric)
        t_target = tuple((1 + (x % 3)) if y > 1 else 0 for y in range(8) for x in range(8))
        t_vanilla = tuple((2 + ((x + y) % 2)) if x > 2 else 0 for y in range(8) for x in range(8))
        t_new = tuple((3 if (x + 2 * y) % 5 == 0 else (1 if x == 1 else 0)) for y in range(8) for x in range(8))
        slot_chars = {0: [t_target, t_vanilla, t_new] + [(0,) * 64] * 61}

        donor_pal128 = [(0, 0, 0)] * 128
        for idx, col in enumerate(((0, 0, 0), (220, 220, 220), (160, 110, 60), (90, 50, 20), (40, 20, 10), (190, 150, 90), (120, 80, 40), (60, 30, 15))):
            donor_pal128[2 * 16 + 8 + idx] = col
        # Tile16 words: Q0=ch0 H-flipped, Q1=ch1, Q2=ch2, Q3=ch2 V-flipped
        w0 = 0 | (2 << 10) | (1 << 14)
        w1 = 1 | (2 << 10)
        w2 = 2 | (2 << 10)
        w3 = 2 | (2 << 10) | (1 << 15)
        donor_tile16s = [(w0, w1, w2, w3)]

        target_cands = D.candidate_subpalettes_from_128(donor_pal128, specs=[(2, True)])
        target_canons = {C.canonical_tile8(t_target, preserve_zero=True)}
        vanilla_canons = {C.canonical_tile8(t_vanilla, preserve_zero=True)}

        res = D.audition_tile16_grid(
            name="TestUnit",
            tile16_grid=[[0]],
            donor_tile16s=donor_tile16s,
            donor_slot_chars=slot_chars,
            donor_pal128=donor_pal128,
            target_candidates=target_cands,
            target_canons=target_canons,
            vanilla_canons=vanilla_canons,
        )
        self.assertEqual(res["unique_new_tile8_cost"], 1)
        statuses = [q["status"] for q in res["quadrants"]]
        self.assertEqual(statuses, ["target_reused", "vanilla_reusable", "marginal_new", "intra_deduped"])

    def test_intent_collectors_and_blast_radius(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            afs = root / "afs"
            (afs / "knowledge" / "planning").mkdir(parents=True)
            (afs / "knowledge" / "planning" / "decisions.org").write_text(
                "* DECIDED Wayward Village $23 test ruling\n  :DOC: test.md\n  Library Room $107 E49 ruling.\n\n"
                "* DECIDED Unrelated Snow Peak\n  Nothing here.\n",
                encoding="utf-8",
            )
            props = root / "proposals" / "wayward-village01"
            props.mkdir(parents=True)
            (props / "PROPOSAL.md").write_text("# Wayward Village study\nCovers $23 and E49.\n", encoding="utf-8")

            # Minimal synthetic 2MB ROM with room header pointer pointing room 0x107 and room 0x05 to blockset 3.
            rom = bytearray(0x200000)
            # Put pointer table at 0x01:8000 -> PC 0x008000, headers at 0x01:9000 -> PC 0x009000
            rom[C.PC_ROOM_HEADER_PTR:C.PC_ROOM_HEADER_PTR + 3] = bytes([0x00, 0x80, 0x01])
            rom[C.PC_ROOM_HEADER_BANK] = 0x01
            for rid, bs in ((0x005, 3), (0x103, 3), (0x107, 3)):
                # Each header at PC 0x9000 + rid*16 -> SNES 0x01:(0x9000 + rid*16)
                snes_lo = (0x9000 + rid * 16) & 0xFFFF
                rom[0x8000 + rid * 2] = snes_lo & 0xFF
                rom[0x8000 + rid * 2 + 1] = (snes_lo >> 8) & 0xFF
                hdr_pc = 0x9000 + rid * 16
                rom[hdr_pc + 1] = 2   # palette
                rom[hdr_pc + 2] = bs  # blockset
                rom[hdr_pc + 3] = 6   # spriteset
            # main_blocksets[3] uses off-limits DMA sheet 0xD7 in slot 0.
            rom[0x6237] = 0x73
            rom[0x6238] = 0xE0
            rom[0x6073 + 3 * 8] = 0xD7

            labels = {"overworld_map": {"0x23": "Wayward Village"}, "room": {"0x005": "Test Dungeon — Room $005", "0x103": "Tavern", "0x107": "Library"}, "entrance": {}, "sprite": {}}
            pats, _ = P._area_search_tokens([0x23], [0x107], labels, [0x49])
            decs = P.collect_decisions(afs, pats)
            self.assertEqual(len(decs), 1)
            self.assertIn("Wayward Village", decs[0]["heading"])

            pdocs = P.collect_design_proposals([root / "proposals"], pats, [0x23])
            self.assertEqual(len(pdocs), 1)
            self.assertIn("wayward-village01/PROPOSAL.md", pdocs[0]["path"])

            br = P.compute_room_blast_radius(bytes(rom), 0x107, labels, {0xD7: {"status": "OFF-LIMITS", "reason": "follower DMA"}})
            self.assertEqual(br["blockset"], "0x03")
            self.assertGreaterEqual(br["rooms_sharing_blockset_count"], 3)
            self.assertTrue(any("0xD7" in w for w in br["off_limits_sheet_warnings"]))

            # Verify staged_ro_rom leaves file untouched and verifies sha256.
            rom_file = root / "test.sfc"
            rom_file.write_bytes(rom)
            before_sha = C.sha256_file(rom_file)
            with C.staged_ro_rom(rom_file) as (copy_path, sha):
                self.assertEqual(sha, before_sha)
                copy_path.write_bytes(b"modified scratch copy only")
            self.assertEqual(C.sha256_file(rom_file), before_sha)


if __name__ == "__main__":
    unittest.main()
