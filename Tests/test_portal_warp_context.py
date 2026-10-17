"""Pure safety controls for the attach-only Portal context fixture; no native calls."""
import importlib.util
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).parent / "native" / "portal_warp_context.py"
SPEC = importlib.util.spec_from_file_location("portal_context_control", PATH)
warp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(warp)


class PortalWarpFixtureControls(unittest.TestCase):
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
