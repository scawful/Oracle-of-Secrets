"""Focused docks writer controls; optional exact-base checks stay in memory.

CI: python3 -m unittest discover -s Tests -p test_kalyxo_docks_bind.py -v
Local: set OOS_TEST_BASE_ROM to the pinned, read-only unpatched base.
"""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Scripts/Generate"))
import kalyxo_docks_bind as writer


class MapFormatTests(unittest.TestCase):
    def test_literal_map_has_exact_extended_header_and_terminator(self):
        cells = bytes(range(256))
        packed = writer.stored(cells)
        self.assertEqual(packed, b"\xe0\xff" + cells + b"\xff")
        self.assertEqual(writer.decode_map(packed, 0), cells)

    def test_legacy_backreference_is_big_endian_and_can_overlap(self):
        # 32 direct bytes, followed by 224 bytes copied from output offset 1.
        # A little-endian interpretation would incorrectly start at offset 256.
        seed = bytes(range(32))
        packed = b"\x1f" + seed + b"\xf0\xdf\x00\x01\xff"
        self.assertEqual(writer.decode_map(packed, 0),
                         seed + bytes(1 + i % 31 for i in range(224)))

    def test_short_and_overlong_maps_are_rejected(self):
        for cells in (bytes(255), bytes(257)):
            with self.subTest(size=len(cells)), self.assertRaises(ValueError):
                writer.decode_map(writer.stored(cells), 0)

    def test_four_map32_ids_match_golden_packed_quadrants(self):
        data = bytearray([0xA5]) * 0x200000
        values = [(0x123, 0x456, 0x789, 0xABC),
                  (0xDEF, 0xFED, 0xCBA, 0x987),
                  (0xF80, 0xF9F, 0xFA2, 0xFBF),
                  (0x005, 0x1A6, 0x2B7, 0x3C8)]
        # Hand-derived six-byte groups, independent of the writer's encoder.
        golden = ["23ef80051df0", "56ed9fa64ff1",
                  "89baa2b77cf2", "bc87bfc8a9f3"]
        allowed = set()
        for index, quadrants in enumerate(values):
            before = writer.definitions32(data)[:4]
            writer.write_definition(data, index, quadrants, allowed)
            after = writer.definitions32(data)[:4]
            self.assertEqual(after[index], quadrants)
            for other in set(range(4)) - {index}:
                self.assertEqual(after[other], before[other])
        self.assertEqual(writer.definitions32(data)[:4], values)
        for base, expected in zip(writer.QUADRANTS, golden):
            self.assertEqual(data[base:base + 6], bytes.fromhex(expected))
            self.assertEqual(data[base - 1], 0xA5)
            self.assertEqual(data[base + 6], 0xA5)
        self.assertEqual(allowed, {base + n for base in writer.QUADRANTS
                                   for n in range(6)})


class BindingAdmissionTests(unittest.TestCase):
    def test_wrong_size_or_hash_refused_before_decoding(self):
        for base in (b"not a ROM", bytes(0x200000)):
            with self.subTest(size=len(base)), \
                    mock.patch.object(writer, "definitions32") as decode, \
                    self.assertRaisesRegex(ValueError, "base identity mismatch"):
                writer.compile_native(base, {})
            decode.assert_not_called()

    def test_cli_refuses_input_or_existing_output_before_asset_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / "base.sfc"
            existing = Path(temporary) / "existing.sfc"
            receipt = Path(temporary) / "receipt.json"
            base.write_bytes(b"base sentinel")
            existing.write_bytes(b"existing sentinel")
            for output in (base, existing):
                arguments = ["kalyxo_docks_bind.py", "--base", str(base),
                             "--out", str(output), "--receipt", str(receipt),
                             "--write-assets"]
                with self.subTest(output=output.name), \
                        mock.patch.object(sys, "argv", arguments), \
                        mock.patch.object(writer, "compile_native") as compile_, \
                        contextlib.redirect_stderr(io.StringIO()), \
                        self.assertRaises(SystemExit) as error:
                    writer.main()
                self.assertEqual(error.exception.code, 2)
                compile_.assert_not_called()
                self.assertFalse(receipt.exists())
                self.assertEqual(base.read_bytes(), b"base sentinel")
                self.assertEqual(existing.read_bytes(), b"existing sentinel")

    def test_real_art_manifest_fits_reserved_cells_and_collision_budget(self):
        directory = ROOT / "Data/graphics/kalyxo_docks/generated"
        art = json.loads((directory / "manifest.json").read_text())
        ids = [cell["id"] for cell in art["cells"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(type(i) is int and 0 <= i < 64 for i in ids))
        unique = (directory / "unique.4bpp").read_bytes()
        self.assertEqual(len(unique), art["unique_subtile_count_with_flips"] * 32)
        self.assertEqual(hashlib.sha256(unique).hexdigest(),
                         art["outputs"]["unique.4bpp"]["sha256"])
        requirements = {"walk": set(), "solid": set()}
        for cell in art["cells"]:
            self.assertEqual([q["quadrant"] for q in cell["subtiles"]],
                             ["tl", "tr", "bl", "br"])
            for q in cell["subtiles"]:
                self.assertIn(q["unique_art_index"], range(len(unique) // 32))
                if cell["collision_intent"] != "unbound" and q["collision_intent"] in requirements:
                    requirements[q["collision_intent"]].add(q["unique_art_index"])
        self.assertLessEqual(len(requirements["walk"]), 18)
        self.assertLessEqual(len(requirements["solid"]), 11)

    def test_cli_refuses_receipt_alias_and_dry_run_asset_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            base = directory / "base.sfc"
            output = directory / "new.sfc"
            base.write_bytes(b"base sentinel")
            cases = [(base, []), (output, []),
                     (directory / "receipt.json", ["--dry-run", "--write-assets"])]
            for receipt, options in cases:
                arguments = ["kalyxo_docks_bind.py", "--base", str(base),
                             "--out", str(output), "--receipt", str(receipt), *options]
                with self.subTest(receipt=receipt.name, options=options), \
                        mock.patch.object(sys, "argv", arguments), \
                        mock.patch.object(writer, "compile_native") as compile_, \
                        contextlib.redirect_stderr(io.StringIO()), \
                        self.assertRaises(SystemExit) as error:
                    writer.main()
                self.assertEqual(error.exception.code, 2)
                compile_.assert_not_called()
                self.assertFalse(output.exists())
                self.assertEqual(base.read_bytes(), b"base sentinel")

    def test_native_passage_stays_in_existing_graphics_areas(self):
        layout = json.loads((ROOT / "Data/overworld/kalyxo_docks.json").read_text())
        seen = set()
        for item in layout["native_placements"]:
            key = (item["screen"], item["x"], item["y"])
            self.assertNotIn(key, seen)
            seen.add(key)
            self.assertIn(item["screen"], (0x32, 0x33))
            self.assertIn(item["x"], range(32))
            self.assertIn(item["y"], range(32))
            self.assertIn(item["tile16"], range(0xF80))
            self.assertIn(item["old_tile16"], range(4096))
        self.assertEqual({p[0] for p in seen}, {0x32, 0x33})
        self.assertEqual(writer.MAPS, (0x30, 0x31, 0x32, 0x33))
        self.assertEqual(writer.PROFILE_MAPS, (0x30, 0x31, 0x32))
        preview = json.loads((ROOT / "Data/graphics/overworld_graphics_preview.json").read_text())
        self.assertNotIn(0x33, {area["parent_map"] for area in preview["areas"]})


@unittest.skipUnless(os.environ.get("OOS_TEST_BASE_ROM"),
                     "set OOS_TEST_BASE_ROM for optional exact-base checks")
class PinnedBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(os.environ["OOS_TEST_BASE_ROM"])
        cls.base = cls.path.read_bytes()
        if hashlib.sha256(cls.base).hexdigest() != writer.BASE_SHA:
            raise AssertionError("OOS_TEST_BASE_ROM is not the pinned audited base")
        cls.layout = json.loads((ROOT / "Data/overworld/kalyxo_docks.json").read_text())
        # compile_native returns bytes in memory; no ROM or asset output path.
        cls.output, cls.bg, cls.binding, cls.receipt = writer.compile_native(cls.base, cls.layout)
        cls.before_defs, cls.after_defs = map(writer.definitions32, (cls.base, cls.output))
        cls.before_maps, cls.after_maps = map(writer.maps32, (cls.base, cls.output))

    @classmethod
    def tearDownClass(cls):
        if cls.path.read_bytes() != cls.base:
            raise AssertionError("read-only base changed during focused checks")

    def test_all_160_maps_only_change_at_declared_dock_and_native_placements(self):
        changed = set()
        placements = {screen: {} for screen in (0x30, 0x31, 0x32, 0x33)}
        for p in self.receipt["placements"]:
            placements[0x30 + p["x"] // 32][p["x"] % 32, p["y"]] = p["tile16"]
        self.assertEqual(self.receipt["native_placements"], self.layout["native_placements"])
        for p in self.layout["native_placements"]:
            self.assertNotIn((p["x"], p["y"]), placements[p["screen"]])
            placements[p["screen"]][p["x"], p["y"]] = p["tile16"]
        for screen in range(160):
            before = writer.expand(self.before_maps[screen], self.before_defs)
            actual = writer.expand(self.after_maps[screen], self.after_defs)
            if actual != before:
                changed.add(screen)
            expected = [row[:] for row in before]
            for (x, y), tile in placements.get(screen, {}).items():
                expected[y][x] = tile
            self.assertEqual(actual, expected, f"screen {screen:02X}")
        self.assertEqual(changed, {0x30, 0x31, 0x32, 0x33})
        self.assertEqual(160 - len(changed), 156)

    def test_loom_passage_reuses_native_donors_and_preserves_their_attributes(self):
        old_ids = {tile for tile32 in self.before_maps[0x33]
                   for tile in self.before_defs[tile32]}
        new_ids = {tile for tile32 in self.after_maps[0x33]
                   for tile in self.after_defs[tile32]}
        self.assertTrue(new_ids <= old_ids)
        for tile in new_ids:
            p = 0x1E8000 + tile * 8
            self.assertEqual(self.output[p:p + 8], self.base[p:p + 8])
        for item in self.layout["native_placements"]:
            before = writer.expand(self.before_maps[item["screen"]], self.before_defs)
            self.assertEqual(before[item["y"]][item["x"]], item["old_tile16"])
            if item["kind"] == "walk_core":
                p = 0x1E8000 + item["tile16"] * 8
                words = [int.from_bytes(self.output[p + q:p + q + 2], "little")
                         for q in (0, 2, 4, 6)]
                # Native grass $034 uses DiggableGround ($48), not the dock's
                # plain-floor $00. Preserve that deliberate donor behavior.
                self.assertEqual([self.output[0x71459 + (word & 511)] for word in words],
                                 [0x48, 0x48, 0x48, 0x48])

    def test_native_passage_refuses_stale_unsafe_and_ambiguous_edits(self):
        changes = [("screen", 0x34, "outside"), ("x", 32, "outside"),
                   ("y", -1, "outside"), ("tile16", writer.FIRST16, "outside"),
                   ("x", True, "outside"),
                   ("old_tile16", self.layout["native_placements"][0]["old_tile16"] ^ 1,
                    "source cell changed")]
        for key, value, message in changes:
            layout = copy.deepcopy(self.layout)
            layout["native_placements"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, message):
                writer.compile_native(self.base, layout)
        layout = copy.deepcopy(self.layout)
        layout["native_placements"].append(layout["native_placements"][0].copy())
        with self.assertRaisesRegex(ValueError, "duplicate or overlapping"):
            writer.compile_native(self.base, layout)
        layout = copy.deepcopy(self.layout)
        layout["native_placements"][0].update(screen=0x32, x=0, y=12)
        with self.assertRaisesRegex(ValueError, "duplicate or overlapping"):
            writer.compile_native(self.base, layout)
        original_ids = {tile for tile32 in self.before_maps[0x32]
                        for tile in self.before_defs[tile32]}
        layout = copy.deepcopy(self.layout)
        layout["native_placements"][0]["tile16"] = next(i for i in range(0xF80)
                                                       if i not in original_ids)
        with self.assertRaisesRegex(ValueError, "donor is not used by its area"):
            writer.compile_native(self.base, layout)

    def test_collision_transition_tables_ship_and_input_are_preserved(self):
        # Yaze overworld.h and ZSCustomOverworld.asm Pool addresses, independent
        # of the writer's allowlist. Includes native and expanded parent tables.
        spans = [(0x71459, 0x200), (0x125EC, 0x40), (0x12634, 0x400),
                 (0x13EE2, 0x100), (0x1788D, 0xA0),
                 (0x140998, 0xA0), (0x140F38, 0x280)]
        for start, size in spans:
            self.assertEqual(self.output[start:start + size], self.base[start:start + size],
                             f"protected span {start:06X}+{size:X}")
        for screen in (0x38, 0x39):
            self.assertEqual(self.after_maps[screen], self.before_maps[screen])
            for tile32 in self.before_maps[screen]:
                self.assertEqual(self.after_defs[tile32], self.before_defs[tile32])
                for tile16 in self.before_defs[tile32]:
                    p = 0x1E8000 + tile16 * 8
                    self.assertEqual(self.output[p:p + 8], self.base[p:p + 8])
            for table in (0x1794D, 0x17B2D):
                p = table + screen * 3
                self.assertEqual(self.output[p:p + 3], self.base[p:p + 3])
        boat = (ROOT / "Overworld/gfx/boat.bin").read_bytes()
        self.assertEqual(self.bg[0x800:], boat[0x800:])
        self.assertEqual(self.path.read_bytes(), self.base)

    def test_bound_chr_cells_have_their_requested_collision_and_budget(self):
        seen = set()
        for cell in self.binding["chr"]:
            slot = cell["chr"]
            self.assertIn(slot, range(0xC0, 0x100))
            self.assertNotIn(slot, seen)
            seen.add(slot)
            self.assertEqual(self.base[0x71459 + slot],
                             {"walk": 0, "solid": 1}[cell["collision_intent"]])
        self.assertLessEqual(self.receipt["stream_pc_end"], 0x228000)
        self.assertEqual(len(self.output), 0x400000)
        self.assertNotIn("ladder_bottom", self.binding["tiles"])
        reservation = json.loads((ROOT / "Data/graphics/source_sprite_sheets.json").read_text())
        start = writer.pc(int(reservation["start"], 16))
        size = reservation["capacity"]
        self.assertEqual(self.output[start:start + size], bytes(size),
                         "expanded source-sprite reservation must remain zero-filled")


if __name__ == "__main__":
    unittest.main()
