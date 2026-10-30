"""B6 ICE kit binding: pixel round trip and live-catalog validation; no ROM/65816."""
from pathlib import Path
import copy
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compile_graphics_pack as pack
import compile_runtime_graphics as runtime
import lyra_b6_ice_binding as b6

FIXTURE = Path(__file__).resolve().parent / "fixtures/lyra_b6_ice"
# Roles used by BOUND_PLACEMENT_RECIPE.json (4165837c); I14/I15 are unplaced.
ROLES = [f"I{n:02d}" for n in range(14)]


def decode_4bpp(data: bytes) -> tuple:
    return tuple(tuple(sum(((data[(p // 2) * 16 + r * 2 + p % 2] >> (7 - x)) & 1) << p
                           for p in range(4)) for x in range(8)) for r in range(8))


class B6IceBindingTests(unittest.TestCase):
    def setUp(self):
        self.page = (FIXTURE / "page-1.3bpp.bin").read_bytes()
        self.words = (FIXTURE / "tiles16.logical.bin").read_bytes()
        self.palette = (FIXTURE / "palette.bgr555.bin").read_bytes()
        self.result = b6.plan(self.page, self.words, ROLES)
        self.allocation = dict(schema_version=1, parent_map=182, palette_row=5, priority=0,
                               chr=list(range(256, 268)),
                               tile16={r: 3900 + i for i, r in enumerate(ROLES)})

    def bound(self, **changes):
        return b6.bind(self.result, self.palette, dict(self.allocation, **changes))

    def test_fixtures_match_reviewed_kit_pins(self):
        for name in ("page-1.3bpp.bin", "tiles16.logical.bin", "palette.bgr555.bin"):
            self.assertEqual(pack.sha256((FIXTURE / name).read_bytes()), b6.PINS[name])

    def test_resource_is_native_high_and_deduped(self):
        self.assertEqual(len(self.result["glyphs"]), 12)
        self.assertEqual(len(self.result["resource"]), 384)
        for at in range(0, 384, 32):
            used = {i for row in decode_4bpp(self.result["resource"][at:at + 32]) for i in row}
            self.assertTrue(used <= {0, *range(9, 16)}, used)

    def test_bound_tile16_words_reproduce_kit_pixels(self):
        records = self.bound()["tile16_records"]
        chars = self.allocation["chr"]
        for role in ROLES:
            logical = 16 + int(role[1:])
            for q, word in enumerate(int(w, 16) for w in records[role]["words_hex"]):
                kit = int.from_bytes(self.words[logical * 8 + q * 2:logical * 8 + q * 2 + 2], "little")
                expected = tuple(tuple(i | 8 if i else 0 for i in row)
                                 for row in b6.decode_3bpp(self.page, (kit & 0x3FF) - 0x40))
                self.assertEqual((word >> 10) & 7, 5)
                self.assertEqual(word & 0x2000, 0)
                glyph = chars.index(word & 0x3FF)
                pixels = decode_4bpp(self.result["resource"][glyph * 32:glyph * 32 + 32])
                self.assertEqual(b6.flip(pixels, bool(word & 0x4000), bool(word & 0x8000)),
                                 expected, f"{role} quadrant {q}")
            self.assertEqual(bytes.fromhex(records[role]["bytes_hex"]),
                             b"".join(int(w, 16).to_bytes(2, "little")
                                      for w in records[role]["words_hex"]))

    def test_fragment_validates_against_live_catalog_and_policy(self):
        fragment = self.bound()
        checked = b6.validate_merged(fragment, self.result,
                                     b6.ROOT / "Overworld/graphics_catalog.json",
                                     b6.ROOT / "Overworld/graphics_runtime_policy.json")
        self.assertEqual(checked["parent"], dict(profile_id="b6-snow-ice", runtime_enabled=False))
        self.assertEqual(checked["lowered_profile"]["cache_slots"], [4])
        self.assertEqual(len(checked["lowered_profile"]["staging"]), 12)
        self.assertEqual({t["type"] for t in fragment["tile_types"]}, {"0E"})

    def test_cache_slots_follow_allocated_characters(self):
        chars = [192, 193, 255, 256, 319, 320, 383, 384, 385, 386, 446, 447]
        policy = self.bound(chr=chars)["policy_fragment"]["b6-snow-ice"]
        self.assertEqual(policy["cache_slots"], [3, 4, 5, 6])

    def test_palette_plan_uses_high_half_without_column_eight(self):
        plan = self.bound(palette_row=3)["palette_plan"]
        self.assertEqual([c["index"] for c in plan["cgram"]], list(range(57, 64)))
        self.assertEqual([c["bgr555"] for c in plan["cgram"]],
                         ["3104", "2D28", "3DEF", "55E7", "6ACF", "7798", "7BFE"])
        self.assertEqual(plan["unused"], [56])

    def test_backdrop_uses_kit_water_word_zero(self):
        plan = b6.backdrop_plan(self.palette)
        self.assertEqual((plan["table"], plan["row"], plan["row_byte_offset"]), ("bg_color", 182, 364))
        self.assertEqual((plan["bgr555"], plan["bytes_hex"]), ("51E8", "e851"))
        self.assertIsNone(plan["address"])
        with self.assertRaises(pack.PackError):
            b6.backdrop_plan(b"\xff\xff" + self.palette[2:])

    def test_rejects_unsafe_allocations(self):
        cases = [dict(chr=list(range(180, 192))), dict(chr=[256] * 12), dict(chr=list(range(256, 267))),
                 dict(parent_map=181), dict(priority=2), dict(palette_row=8),
                 dict(tile16={r: 3900 for r in ROLES}), dict(tile16={"I00": 1}),
                 dict(tile16={r: 4096 + i for i, r in enumerate(ROLES)})]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(pack.PackError):
                self.bound(**change)

    def test_rejects_second_binding_for_parent_182(self):
        fragment = self.bound()
        twice = copy.deepcopy(fragment)
        twice["catalog_fragment"]["bindings"] *= 2
        with self.assertRaises(pack.PackError):
            b6.validate_merged(twice, self.result, b6.ROOT / "Overworld/graphics_catalog.json",
                               b6.ROOT / "Overworld/graphics_runtime_policy.json")

    def test_authoring_contract_rejects_opaque_index_eight(self):
        fragment = self.bound()
        resource = bytearray(self.result["resource"])
        resource[17] = 0xFF  # glyph 0 row 0: plane 3 only = index 8
        for offset in (0, 1, 16):
            resource[offset] = 0
        catalog = dict(schema_version=2, **copy.deepcopy(fragment["catalog_fragment"]))
        with self.assertRaisesRegex(pack.PackError, "forbidden opaque index 8"):
            runtime.validate_authoring_contracts(
                catalog, {self.result["resource_id"]: bytes(resource)})

    def test_type_report_flags_characters_shared_with_other_maps(self):
        rom = bytearray(b6.TILE_TYPES_PC + 512)
        rom[b6.TILE_TYPES_PC + 256] = 0x0E
        rom[b6.TILE_TYPES_PC + 257] = 0x02
        report = b6.tile_type_report(bytes(rom), [257, 256])
        self.assertEqual([(r["chr"], r["changes_other_maps"]) for r in report],
                         [(256, False), (257, True)])

    def test_rejects_flipped_or_off_page_kit_words(self):
        words = bytearray(self.words)
        words[16 * 8 + 1] |= 0x40  # I00 top-left gains h-flip
        with self.assertRaises(pack.PackError):
            b6.plan(self.page, bytes(words), ROLES)
        with self.assertRaises(pack.PackError):
            b6.plan(self.page, self.words, ["S00"])


if __name__ == "__main__":
    unittest.main()
