"""Pure safety controls for the attach-only Portal context fixture; no native calls."""
import importlib.util
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

PATH = Path(__file__).parent / "native" / "portal_warp_context.py"
SPEC = importlib.util.spec_from_file_location("portal_context_control", PATH)
warp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(warp)


class PortalWarpFixtureControls(unittest.TestCase):
    def assert_cli_identity_admission(self, correct_sha1):
        # Exercise actual argparse/main admission with synthetic bytes. Stop at
        # describe(), before output creation or any native bridge import/call.
        class AdmissionReached(Exception):
            pass

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image, symbols = b"synthetic CLI identity fixture", b"synthetic symbols\n"
            rom, sym, output = root / "test.sfc", root / "test.sym", root / "output"
            rom.write_bytes(image)
            sym.write_bytes(symbols)
            sha1 = hashlib.sha1(image).hexdigest().upper() if correct_sha1 else "0" * 40
            arguments = [str(PATH), "--socket", str(root / "unused.sock"),
                         "--status-file", str(root / "unused.status"), "--pid", "123",
                         "--owned-rom", str(rom), "--rom-sha256", hashlib.sha256(image).hexdigest(),
                         "--rom-sha1", sha1, "--symbols", str(sym),
                         "--symbols-sha256", hashlib.sha256(symbols).hexdigest(),
                         "--client-root", str(root), "--owner", "pure-cli-control",
                         "--owner-file", str(root / "unused-owner.json"), "--output", str(output),
                         "--support-file", str(root / "unused-support.py"), "--world", "dungeon",
                         "--color", "blue", "--expect", "baseline", "--execute-fixtures"]
            with mock.patch.object(sys, "argv", arguments), \
                    mock.patch.object(warp, "describe", side_effect=AdmissionReached) as describe:
                if correct_sha1:
                    with self.assertRaises(AdmissionReached):
                        warp.main()
                    describe.assert_called_once_with(image, symbols.decode(), "baseline")
                else:
                    with self.assertRaisesRegex(RuntimeError, "ROM/symbol identities differ"):
                        warp.main()
                    describe.assert_not_called()
            self.assertFalse(output.exists())
            self.assertEqual(rom.read_bytes(), image)
            self.assertEqual(sym.read_bytes(), symbols)

    def test_actual_cli_accepts_uppercase_matching_sha1_before_native_admission(self):
        self.assert_cli_identity_admission(True)

    def test_actual_cli_refuses_wrong_sha1_before_native_admission(self):
        self.assert_cli_identity_admission(False)

    def test_search_preserves_original_order_and_bounds_new_candidates(self):
        targets = warp.near_targets(0x7B8, 0xD8B, 0x740, 0xD2B)
        self.assertEqual(targets[:8], [(0x7C8, 0xD9B), (0x7A8, 0xD9B),
                                      (0x7C8, 0xD7B), (0x7A8, 0xD7B),
                                      (0x7C8, 0xD8B), (0x7A8, 0xD8B),
                                      (0x7B8, 0xD9B), (0x7B8, 0xD7B)])
        self.assertLessEqual(len(targets), 1024)
        self.assertEqual(len(set(targets)), len(targets))
        self.assertNotIn((0x7B8, 0xD8B), targets)
        for x, y in targets[8:]:
            self.assertEqual((x >> 8, y >> 8), (7, 13))
            self.assertEqual((x & 7, y & 7), (0, 0))
            self.assertTrue(0 <= x - 0x740 <= 0xEF and 0 <= y - 0xD2B <= 0xC7)
        keys = [(abs(x - 0x7B8) + abs(y - 0xD8B), y, x) for x, y in targets[8:]]
        self.assertEqual(keys, sorted(keys))

    def test_broader_search_keeps_the_first_original_success(self):
        probe = warp.floor_probe(warp.near_targets(0x7B8, 0xD8B, 0x740, 0xD2B),
                                 lambda x, y: 0, (0x740, 0xD2B))
        self.assertEqual((probe["x"], probe["y"], probe["buttons"]), (0x7C8, 0xD9B, "RIGHT"))

    def test_broader_search_finds_a_separate_verified_floor_island(self):
        # A controlled independent island, outside all original +/-16 choices.
        def attr(x, y):
            return 0 if 0x748 <= x <= 0x760 and 0xD80 <= y <= 0xD98 else 1

        targets = warp.near_targets(0x7B8, 0xD8B, 0x740, 0xD2B)
        with self.assertRaisesRegex(RuntimeError, "No read-only verified"):
            warp.floor_probe(targets[:8], attr, (0x740, 0xD2B))
        probe = warp.floor_probe(targets, attr, (0x740, 0xD2B))
        self.assertEqual((probe["x"], probe["y"], probe["buttons"]), (0x750, 0xD80, "LEFT"))
        self.assertTrue(all(value == 0 for _, _, value in probe["samples"]))

    def test_safe_floor_outside_actual_page_or_view_does_not_admit_a_target(self):
        targets = warp.near_targets(0x7B8, 0xD8B, 0x740, 0xD2B)
        for attr in (lambda x, y: 0 if x >= 0x800 else 1,
                     lambda x, y: 0 if x < 0x740 else 1,
                     lambda x, y: 0x48):
            with self.assertRaisesRegex(RuntimeError, "No read-only verified"):
                warp.floor_probe(targets, attr, (0x740, 0xD2B))

    def test_failed_selection_retains_attempts_and_reads_each_cell_only_once(self):
        calls, trace = {}, {}

        def attr(x, y):
            calls[x, y] = calls.get((x, y), 0) + 1
            return 2

        with self.assertRaisesRegex(RuntimeError, "No read-only verified"):
            warp.floor_probe([(0x7A0, 0xD80), (0x7A8, 0xD80)], attr, (0x740, 0xD2B), trace)
        self.assertEqual(trace["outcome"], "no-safe-corridor")
        self.assertEqual(len(trace["attempts"]), 8)
        self.assertTrue(all(row["outcome"] == "unsafe-floor" and row["samples"]
                            for row in trace["attempts"]))
        self.assertTrue(all(count == 1 for count in calls.values()))
        self.assertEqual(len(trace["unique_reads"]), len(calls))
        self.assertGreater(trace["cache_hits"], 0)
        with self.assertRaisesRegex(RuntimeError, "finite bound"):
            warp.floor_probe([(0x7A0, 0xD80)] * 1025, attr)

    def test_floor_read_cache_does_not_cross_selections(self):
        warp.floor_probe([(0x7A0, 0xD80)], lambda x, y: 0)
        with self.assertRaisesRegex(RuntimeError, "No read-only verified"):
            warp.floor_probe([(0x7A0, 0xD80)], lambda x, y: 1)

    def test_actual_jsr_return_requires_two_popped_stack_bytes(self):
        entry = dict(sp=0x1E8, x=0, y=14, dbr=0x31, d=0, p=0x32)
        returned = dict(entry, sp=0x1EA, p=0x33)
        warp.check_context_return(entry, returned, True)
        with self.assertRaisesRegex(RuntimeError, "short-return"):
            warp.check_context_return(entry, dict(returned, sp=entry["sp"]), True)

    def test_context_return_refuses_lost_target_y_and_other_flag_changes(self):
        entry = dict(sp=0x1E8, x=0, y=14, dbr=0x31, d=0, p=0x32)
        returned = dict(entry, sp=0x1EA, p=0x32)
        warp.check_context_return(entry, returned, False)
        for field, value in (("y", 0), ("dbr", 0x02), ("d", 1), ("p", 0xB2), ("p", 0x33)):
            with self.assertRaisesRegex(RuntimeError, "short-return"):
                warp.check_context_return(entry, dict(returned, **{field: value}), False)

    def test_floor_probe_refuses_hazard_under_the_landing(self):
        with self.assertRaisesRegex(RuntimeError, "No read-only verified"):
            warp.floor_probe([(0x978, 0x2178)], lambda x, y: 1 if (x, y) == (0x980, 0x2180) else 0)

    def test_floor_probe_includes_native_feet_below_the_visible16px_box(self):
        with self.assertRaisesRegex(RuntimeError, "No read-only verified"):
            warp.floor_probe([(0x978, 0x2178)], lambda x, y: 1 if y == 0x2188 else 0)

    def test_floor_probe_chooses_only_a_read_only_walkable_corridor(self):
        p = warp.floor_probe([(0x978, 0x2178)], lambda x, y: 0)
        self.assertEqual((p["x"], p["y"], p["buttons"]), (0x978, 0x2178, "RIGHT"))
        self.assertTrue(p["samples"])
        self.assertEqual({v for _, _, v in p["samples"]}, {0})

    def test_short_probe_cannot_cross_the_admitted_page(self):
        p = warp.floor_probe([(0x9F8, 0x2178)], lambda x, y: 0, (0x980, 0x2100))
        self.assertEqual(p["buttons"], "LEFT")

    def test_completion_requires_exact_target_camera_layer_and_normal_control(self):
        state = dict(module=7, submodule=0, movement=0, recovery_stage=0,
                     xy=[0x988, 0x2188], primary_camera=[0x900, 0x2100], layer=0)
        warp.check_completed_state(state, (0x988, 0x2188), "dungeon", [0x900, 0x2100], 0)
        for field, value in (("module", 9), ("submodule", 0x14), ("movement", 1),
                             ("xy", [0x978, 0x2178]), ("primary_camera", [0x900, 0x2000]), ("layer", 1)):
            with self.assertRaisesRegex(RuntimeError, "exact target"):
                warp.check_completed_state(dict(state, **{field: value}), (0x988, 0x2188),
                                           "dungeon", [0x900, 0x2100], 0)

    def test_native12bit_map16_high_ids_use_the_full_definition_bank(self):
        # Existing walkable Tile322103 uses Tile16C0A/C0B/BEC; these are valid
        # definition records beyond a mistaken16KiB half-bank limit.
        self.assertEqual(warp.ow_definition_offset(0xC0A, 0, 0), 0x6050)
        self.assertEqual(warp.ow_definition_offset(0xFFF, 8, 8), 0x7FFE)
        with self.assertRaisesRegex(RuntimeError, "12bit"):
            warp.ow_definition_offset(0x1000, 0, 0)

    def test_import_does_not_load_native_bridge(self):
        self.assertNotIn("mesen2_client_lib.bridge", sys.modules)

    def test_whitelist_excludes_player_camera_module_and_save(self):
        for start, length in ((0x7E0020, 4), (0x7E00E0, 12), (0x7E0600, 32),
                              (0x7E0010, 2), (0x7E00B0, 1), (0x7EF000, 0x500),
                              (0x700000, 8192), (0x7E037B, 1), (0x7EF36D, 1)):
            for address in range(start, start + length):
                self.assertFalse(warp.allowed_write(address), hex(address))

    def test_only_native_cache_owned_fields_can_be_poisoned(self):
        self.assertEqual(len(warp.FIXTURE_CACHE), 37)
        for address in range(0x7EC180, 0x7EC1AB):
            self.assertEqual(warp.allowed_write(address), address not in range(0x7EC1A0, 0x7EC1A6))
        for address in (0x7EC17F, 0x7EC1AB, 0x7EC200):
            self.assertFalse(warp.allowed_write(address))

    def test_other_sprite_slots_have_state_only_cleanup_permission(self):
        for slot in range(16):
            self.assertTrue(warp.allowed_write(0x7E0DD0 + slot))
            if slot not in (0, 14):
                for table in (0xD00, 0xD10, 0xD20, 0xD30, 0xF20, 0xEE0, 0xE20, 0xE30):
                    self.assertFalse(warp.allowed_write(0x7E0000 + table + slot))

    def test_cross_page_inputs_are_nearby_but_change_actual_link_page(self):
        for x, y in ((0x0978, 0x2178), (0x09F8, 0x21F8), (0x0908, 0x2108)):
            tx, ty, layer = warp.target_case("cross-x", x, y, 0x0900, 0x2100, 1)
            self.assertEqual((tx, ty, layer), (x ^ 0x100, y, 1))
            tx, ty, layer = warp.target_case("cross-y", x, y, 0x0900, 0x2100, 0)
            self.assertEqual((tx, ty, layer), (x, y ^ 0x100, 0))

    def test_offscreen_inputs_keep_link_pages_and_layer(self):
        for x, y, sx, sy in ((0x0978, 0x2178, 0x0900, 0x2100),
                              (0x09A0, 0x2190, 0x0980, 0x2180),
                              (0x0910, 0x2110, 0x08F0, 0x20F0)):
            for name, axis, limit, scroll in (("offscreen-x", 0, 0xF0, sx), ("offscreen-y", 1, 0xD0, sy)):
                target = warp.target_case(name, x, y, sx, sy, 1)
                self.assertEqual((target[0] >> 8, target[1] >> 8, target[2]), (x >> 8, y >> 8, 1))
                self.assertGreater((target[axis] - scroll) & 65535, limit)

    def test_positive_target_moves_both_axes_inside_current_context(self):
        for x, y, sx, sy in ((0x0978, 0x2178, 0x0900, 0x2100),
                              (0x09E0, 0x21C0, 0x0900, 0x2100),
                              (0x0990, 0x2190, 0x0980, 0x2180)):
            tx, ty, layer = warp.target_case("near", x, y, sx, sy, 1)
            self.assertEqual((abs(tx - x), abs(ty - y)), (16, 16))
            self.assertEqual((tx >> 8, ty >> 8, layer), (x >> 8, y >> 8, 1))
            self.assertLessEqual((tx - sx) & 65535, 0xF0)
            self.assertLessEqual((ty - sy) & 65535, 0xD0)

    def test_layer_refusal_keeps_full_coordinates_and_invalid_name_refuses(self):
        self.assertEqual(warp.target_case("other-layer", 0x0978, 0x2178, 0x900, 0x2100, 0), (0x978, 0x2178, 1))
        with self.assertRaisesRegex(RuntimeError, "Unknown context"):
            warp.target_case("unknown", 0x978, 0x2178, 0x900, 0x2100, 0)


if __name__ == "__main__":
    unittest.main()
