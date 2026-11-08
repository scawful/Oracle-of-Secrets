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

    def test_wall_scope_reports_the_boundary_gap(self):
        _, result = self.check("hallows_0da_moved.objects.json",
                               "hallows_0da_moved_good.trace.json", "all")
        self.assertEqual(result["status"], "UNSUPPORTED")

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


if __name__ == "__main__":
    unittest.main()
