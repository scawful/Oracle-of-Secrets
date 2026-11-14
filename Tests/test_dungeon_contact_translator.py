"""dungeon_contact_translator v0: translate, refuse unmeasured contacts, guard ROMs,
and build checker contracts that the unchanged preflight accepts or blocks."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ROOMS = ROOT / "Scripts/Rooms"
FIXTURES = ROOMS / "tests/fixtures/dungeon_layout/contact_translator"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOMS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


translator = load("dungeon_contact_translator")
preflight = load("dungeon_layout_preflight")
HALLOWS = "hallows_0da_south_stair_wall_cut"


def packet(room="0xDA", **contact):
    base = {"name": "da_mouth", "family": HALLOWS, "anchor": [38, 47]}
    base.update(contact)
    return {"schema_version": 1, "room_id": room, "contacts": [base]}


class Translate(unittest.TestCase):
    def setUp(self):
        self.library = translator.load_library()

    def test_library_holds_the_three_measured_contacts(self):
        self.assertEqual(sorted(self.library), ["alttp_61_dais_cutin_north", HALLOWS,
                                                "oracle_cc_spiral_wall_cut"])

    def test_translation_keeps_ids_sizes_lists_and_order(self):
        result, code = translator.translate(packet(), self.library)
        self.assertEqual(code, 0)
        members = self.library[HALLOWS]["members"]
        self.assertEqual([(o["object_id"], o["size"], o["list"]) for o in result["objects"]],
                         [(m["object_id"], m["size"], m["list"]) for m in members])
        self.assertEqual([o["role"] for o in result["objects"]], ["wall", "stair"])
        self.assertEqual(result["contacts"][0]["translation_from_source"], [8, 0])
        stair = result["objects"][1]
        self.assertEqual((stair["object_id"], stair["x"], stair["y"]), ("0xF9D", 38, 47))

    def test_every_family_translates_at_its_source_anchor(self):
        for name, family in self.library.items():
            p = {"schema_version": 1, "room_id": family["source"]["room_id"],
                 "contacts": [{"name": "c", "family": name, "anchor": family["source"]["anchor"]}]}
            result, code = translator.translate(p, self.library)
            self.assertEqual(code, 0, name)
            self.assertEqual(result["contacts"][0]["translation_from_source"], [0, 0])

    def test_unmeasured_contacts_are_unsupported(self):
        cases = {"facing": "north", "rotation": 90, "mirror": True,
                 "family": "hallows_0da_north_stair_wall_cut", "anchor": [62, 47]}
        for key, value in cases.items():
            with self.subTest(key=key):
                result, code = translator.translate(packet(**{key: value}), self.library)
                self.assertEqual((code, result["status"], result["objects"]), (1, "UNSUPPORTED", []))
                self.assertTrue(result["unsupported"][0]["reason"])

    def test_overlapping_contacts_are_unsupported(self):
        p = packet()
        p["contacts"].append({"name": "second", "family": HALLOWS, "anchor": [39, 47]})
        result, code = translator.translate(p, self.library)
        self.assertEqual(code, 1)
        self.assertIn("overlaps", result["unsupported"][0]["reason"])

    def test_relocate_source_removes_members_highest_index_first(self):
        result, _ = translator.translate(packet(), self.library, relocate_source=True)
        self.assertEqual([r["index"] for r in result["removals"]], [57, 56])
        self.assertEqual((result["removals"][1]["x"], result["removals"][1]["y"]), (25, 47))
        with self.assertRaises(translator.InputError):
            translator.translate(packet(room="0x10"), self.library, relocate_source=True)


class RomGuard(unittest.TestCase):
    def test_refuses_shared_and_project_paths(self):
        with tempfile.TemporaryDirectory() as d:
            for part in ("Roms", "x.yazeproj"):
                path = Path(d) / part / "rom.sfc"
                path.parent.mkdir()
                path.write_bytes(b"\0" * 16)
                with self.assertRaises(translator.InputError):
                    translator.guard_scratch_rom(path)

    def test_refuses_protected_sha_and_accepts_scratch(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "scratch.sfc"
            path.write_bytes(b"\0" * 16)
            self.assertEqual(translator.guard_scratch_rom(path)[1], hashlib.sha256(b"\0" * 16).hexdigest())
            digest = hashlib.sha256(b"\0" * 16).hexdigest()[:8]
            old = translator.PROTECTED_SHA_PREFIXES
            translator.PROTECTED_SHA_PREFIXES = (digest,)
            try:
                with self.assertRaises(translator.InputError):
                    translator.guard_scratch_rom(path)
            finally:
                translator.PROTECTED_SHA_PREFIXES = old

    def test_apply_refuses_unsupported_object_list(self):
        with self.assertRaises(translator.InputError):
            translator.apply_objects({"status": "UNSUPPORTED"}, "unused.sfc", "z3ed", False)


class Contract(unittest.TestCase):
    """Fixtures are the Hallows contact cut from real z3ed traces (scratch round trip, 2026-11-08)."""

    def setUp(self):
        self.library = copy.deepcopy(translator.load_library())
        ref = FIXTURES / "hallows_0da_reference.trace.json"
        self.library[HALLOWS]["source"]["trace"] = ref.name
        self.library[HALLOWS]["source"]["trace_sha256"] = translator.sha256(ref)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def check(self, objects, trace, require):
        doc = json.loads((FIXTURES / objects).read_text())
        out = Path(self.temp.name) / f"{require}.contract.json"
        contract = translator.build_contract(doc, FIXTURES / trace, out, self.library, FIXTURES, require)
        out.write_text(json.dumps(contract))
        return contract, preflight.check(contract, FIXTURES / trace, out.parent)

    def test_round_trip_passes_stair_scope(self):
        contract, result = self.check("hallows_0da_moved.objects.json",
                                      "hallows_0da_moved_good.trace.json", "stair")
        self.assertEqual(contract["assemblies"][0]["candidate"]["object_indices"], [123, 124])
        self.assertEqual(result["status"], "PASS")

    def test_wall_scope_passes_through_stair_mouth_boundary(self):
        contract, result = self.check("hallows_0da_moved.objects.json",
                                      "hallows_0da_moved_good.trace.json", "all")
        self.assertEqual([b["kind"] for b in contract["wall_boundaries"]], ["stair_mouth"])
        self.assertEqual(result["status"], "PASS", result["errors"] + result["unsupported"])

    def test_wall_scope_blocks_stair_before_wall(self):
        _, result = self.check("hallows_0da_moved_wrong_order.objects.json",
                               "hallows_0da_moved_wrong_order.trace.json", "all")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("STAIR_MOUTH_ORDER", [e["code"] for e in result["errors"]])

    def test_stair_before_wall_is_blocked(self):
        contract, result = self.check("hallows_0da_moved_wrong_order.objects.json",
                                      "hallows_0da_moved_wrong_order.trace.json", "stair")
        self.assertEqual(contract["assemblies"][0]["candidate"]["object_indices"], [124, 123])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("ASSEMBLY_MISMATCH", [e["code"] for e in result["errors"]])

    def test_reference_sha_mismatch_is_refused(self):
        self.library[HALLOWS]["source"]["trace_sha256"] = "0" * 64
        with self.assertRaises(translator.InputError):
            self.check("hallows_0da_moved.objects.json", "hallows_0da_moved_good.trace.json", "stair")


PATHFINDER = (Path.home() / ".context/projects/oracle-of-secrets/scratchpad/handoffs/zora_design_review_2026-11-06/"
              "mask-route-check-2026-11-08/merge-proof/tools/scene-director-9f721704/"
              "Scripts/Agents/scene_director/pathfind.py")
ZORA_LOW_STEP_CELLS = [[31, 26, 0], [32, 26, 0], [31, 27, 0], [32, 27, 0],
                       [13, 40, 0], [14, 40, 0], [13, 41, 0], [14, 41, 0]]


def type2(object_id, x, y):
    return bytes([0xFC | x >> 4, (x & 15) << 4 | y >> 2, (y & 3) << 6 | object_id & 0x3F])


class DrySteps(unittest.TestCase):
    """Zora room 0x25 v5 streams and RAM collision replays (Codex-Zora-Delivery, 2026-11-14)."""

    def setUp(self):
        self.rule = translator.load_dry_steps()["north_merged_dry_step_132"]
        self.low = (FIXTURES / "zora25_low_v5.stream.bin").read_bytes()
        self.low_attrs = translator.read_collision(FIXTURES / "zora25_low_v5.collision.bin")
        self.writer = translator.load_module("sky_d8_room_writer", ROOMS / "sky_d8_room_writer.py")

    def edit(self, insert):
        """Low stream with records inserted into list 0 at {position: record}."""
        stream = self.writer.parse_object_stream(self.low, 0, len(self.low))
        primary = list(stream.lists[0])
        for position in sorted(insert, reverse=True):
            primary.insert(position, insert[position])
        raw, _ = self.writer.encode_object_stream(stream.header, [primary, *stream.lists[1:]], stream.doors)
        return raw

    def classify(self, raw=None, attrs=None):
        return translator.classify_steps(raw or self.low, attrs or self.low_attrs, self.rule)

    def test_low_admits_only_the_two_measured_step_cores(self):
        result, code = self.classify()
        self.assertEqual((code, result["status"]), (0, "OK"), result["unsupported"] + result["errors"])
        self.assertEqual(result["stream_sha256"], self.rule["measured"][0]["stream_sha256"])
        self.assertEqual([s["origin"] for s in result["steps"]], [[30, 25], [12, 39]])
        self.assertEqual(result["admitted_cells"], ZORA_LOW_STEP_CELLS)
        self.assertEqual(result["unclassified_step_cells"], [])

    def test_high_wet_133_and_135_are_refused(self):
        raw = (FIXTURES / "zora25_high_v5.stream.bin").read_bytes()
        attrs = translator.read_collision(FIXTURES / "zora25_high_v5.collision.bin")
        result, code = self.classify(raw, attrs)
        self.assertEqual((code, result["status"], result["admitted_cells"]), (1, "UNSUPPORTED", []))
        refused = {(u["object_id"], tuple(u["origin"])) for u in result["unsupported"] if "object_id" in u}
        self.assertEqual(refused, {("0x133", (30, 25)), ("0x133", (12, 39)), ("0x135", (42, 25)),
                                   ("0x135", (16, 39)), ("0x135", (51, 39))})

    def test_wet_follower_drawn_before_a_dry_step_is_blocked(self):
        primary = self.writer.parse_object_stream(self.low, 0, len(self.low)).lists[0]
        first = next(n for n, r in enumerate(primary) if r[0] >= 0xFC and r[2] & 0x3F == 0x32)
        for position in (first, first + 1):
            with self.subTest(position=position):
                result, code = self.classify(self.edit({position: type2(0x136, 42, 25)}))
                self.assertEqual((code, result["status"], result["admitted_cells"]), (1, "BLOCKED", []))
                self.assertEqual([e["code"] for e in result["errors"]], ["STEP_SLOT_ORDER"])

    def test_wet_follower_after_every_dry_step_keeps_the_cells(self):
        primary = self.writer.parse_object_stream(self.low, 0, len(self.low)).lists[0]
        result, code = self.classify(self.edit({len(primary): type2(0x136, 42, 25)}))
        self.assertEqual((code, result["admitted_cells"]), (0, ZORA_LOW_STEP_CELLS))
        self.assertEqual([w["object_id"] for w in result["wet_followers"]], ["0x136"])

    def test_objects_that_change_044A_or_reuse_the_slots_are_refused(self):
        records = {"0x130": type2(0x130, 42, 25), "0x131": type2(0x131, 42, 25),
                   "0x133": type2(0x133, 42, 25), "0x135": type2(0x135, 42, 25),
                   "0xF9B": self.writer.encode_type3(0xF9B, 42, 25),
                   "0xF9C": self.writer.encode_type3(0xF9C, 42, 25),
                   "0x0D8": bytes([42 * 4, 25 * 4, 0xD8]), "0x0DA": bytes([42 * 4, 25 * 4, 0xDA]),
                   "0x137": type2(0x137, 42, 25)}
        self.assertEqual(sorted(records), sorted(self.rule["refuse"]))
        for name, record in records.items():
            for position in (0, 41):
                with self.subTest(object_id=name, position=position):
                    result, code = self.classify(self.edit({position: record}))
                    self.assertEqual((code, result["status"], result["admitted_cells"]), (1, "UNSUPPORTED", []))
                    self.assertIn(name, [u.get("object_id") for u in result["unsupported"]])

    def test_slot_overflow_is_refused(self):
        primary = self.writer.parse_object_stream(self.low, 0, len(self.low)).lists[0]
        end = len(primary)
        result, code = self.classify(self.edit({end: type2(0x136, 42, 25), end + 1: type2(0x136, 16, 39),
                                                end + 2: type2(0x136, 51, 39)}))
        self.assertEqual((code, result["status"]), (1, "UNSUPPORTED"))
        self.assertIn("exceed the 4 native slots", result["unsupported"][0]["reason"])

    def test_replay_that_differs_from_the_native_stamp_is_refused(self):
        for cell, plane in (((31, 26), 0), ((13, 42), 0), ((12, 42), 1)):
            with self.subTest(cell=cell, plane=plane):
                attrs = bytearray(self.low_attrs)
                attrs[plane * 4096 + cell[1] * 64 + cell[0]] ^= 0x1D
                result, code = self.classify(attrs=bytes(attrs))
                self.assertEqual((code, result["status"], result["admitted_cells"]), (1, "UNSUPPORTED", []))
                self.assertEqual(result["unsupported"][0]["cells"][0][:3], [plane, *cell])

    def test_stray_1D_cells_stay_transitions(self):
        attrs = bytearray(self.low_attrs)
        attrs[20 * 64 + 40] = 0x1D
        result, code = self.classify(attrs=bytes(attrs))
        self.assertEqual((code, result["admitted_cells"]), (0, ZORA_LOW_STEP_CELLS))
        self.assertEqual(result["unclassified_step_cells"], [[40, 20, 0]])

    def test_route_refuses_an_unclassified_state(self):
        with self.assertRaises(translator.InputError):
            translator.route_steps({"status": "UNSUPPORTED"}, self.low_attrs, PATHFINDER, (456, 120), (112, 272))

    @unittest.skipUnless(PATHFINDER.exists(), "pinned scene_director pathfinder copy is not on this host")
    def test_route_uses_only_admitted_cells_and_keeps_the_default_refusal(self):
        steps, _ = self.classify()
        route, code = translator.route_steps(steps, self.low_attrs, PATHFINDER, (456, 120), (112, 272))
        self.assertEqual((code, route["status"]), (0, "MODEL_PATH"))
        self.assertEqual(route["default_find_path"], "NeedsRoomChangeError")
        self.assertEqual(route["waypoints"], [[456, 120], [248, 120], [248, 336], [104, 336], [104, 272], [112, 272]])
        self.assertEqual([c + [0] for c in route["transition_cells_used"]], ZORA_LOW_STEP_CELLS)

    @unittest.skipUnless(PATHFINDER.exists(), "pinned scene_director pathfinder copy is not on this host")
    def test_route_avoids_an_unadmitted_1D_on_its_corridor(self):
        attrs = bytearray(self.low_attrs)
        attrs[16 * 64 + 45] = 0x1D
        steps, _ = self.classify(attrs=bytes(attrs))
        route, code = translator.route_steps(steps, bytes(attrs), PATHFINDER, (456, 120), (112, 272))
        self.assertEqual((code, route["status"]), (0, "MODEL_PATH"))
        self.assertEqual([c + [0] for c in route["transition_cells_used"]], ZORA_LOW_STEP_CELLS)
        self.assertNotEqual(route["waypoints"][1], [248, 120])

    @unittest.skipUnless(PATHFINDER.exists(), "pinned scene_director pathfinder copy is not on this host")
    def test_route_that_enters_a_step_sideways_is_unsupported(self):
        attrs = bytearray(self.low_attrs)
        for x, y in ((10, 41), (11, 41), (12, 41), (12, 42)):
            attrs[y * 64 + x] = 0x00
        steps, code = self.classify(attrs=bytes(attrs))
        self.assertEqual(code, 0)
        route, code = translator.route_steps(steps, bytes(attrs), PATHFINDER, (80, 320), (104, 288))
        self.assertEqual((code, route["status"]), (1, "UNSUPPORTED"))
        self.assertTrue(route["sideways_step_moves"])


if __name__ == "__main__":
    unittest.main()
