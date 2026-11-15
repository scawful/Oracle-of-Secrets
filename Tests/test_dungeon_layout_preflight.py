"""Read-only native trace regressions; fixtures are captures, not a renderer."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "Scripts/Rooms/dungeon_layout_preflight.py"
SPEC = importlib.util.spec_from_file_location("dungeon_layout_preflight", SCRIPT)
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)
FIXTURES = ROOT / "Scripts/Rooms/tests/fixtures/dungeon_layout"
SITES = [("northwest", 31, 39, 0x108), ("northeast", 58, 39, 0x10A),
         ("left_bend", 31, 44, 0x063), ("bottom_left_turn", 27, 55, 0x109)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contract(path):
    return {"schema_version": 1, "room_id": 38, "state_profile": "default",
            "provenance": {"candidate_trace_sha256": sha(path)},
            "required_object_indices": [], "assemblies": [],
            "owner_expectations": [{"name": name, "bg": 0, "x": x, "y": y,
                                    "allowed_object_ids": [owner]} for name, x, y, owner in SITES]}


class DungeonLayoutPreflight(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def save(self, name, value):
        path = self.directory / name
        path.write_text(json.dumps(value))
        return path

    def run_check(self, plan, path):
        return preflight.check(plan, path, self.directory)

    def assembly(self, delta=(0, 0)):
        reference = FIXTURES / "v11_good.json"
        data = json.loads(reference.read_text())
        reference_indices = [c["object_index"] for c in data["cases"]]
        dx, dy = delta
        for c in data["cases"]:
            c["object_index"] += 1000
            c["object_x"] += dx
            c["object_y"] += dy
            for t in c["tiles"]:
                t["x_tile"] += dx
                t["y_tile"] += dy
        path = self.save("candidate.json", data)
        plan = contract(path)
        plan["owner_expectations"] = []
        # These tests scope native write comparison only. Changed wall placement
        # admission is exercised by the separate required-boundary controls.
        candidate_indices = [i + 1000 for i in reference_indices]
        plan["assemblies"] = [{"name": "captured native write group (test only)",
                              "reference": {"trace": str(reference), "sha256": sha(reference),
                                            "object_indices": reference_indices},
                              "candidate": {"object_indices": candidate_indices},
                              "translation": [dx, dy]}]
        return plan, path, data

    def test_actual_v10_control_reports_four_final_frame_owners(self):
        path = FIXTURES / "v10_bad.json"
        result = self.run_check(contract(path), path)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual([e["actual"]["object_id"] for e in result["errors"]],
                         [0x100, 0x102, 0x104, 0x105])
        self.assertEqual({e["actual"]["stream_list"] for e in result["errors"]}, {2})

    def test_actual_v11_retaining_owners_pass_only_declared_sites(self):
        path = FIXTURES / "v11_good.json"
        result = self.run_check(contract(path), path)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["checked"]["owner_expectations"], 4)
        self.assertIn("not room approval", result["scope"])

    def test_trace_json_order_does_not_replace_native_pass_order(self):
        original = FIXTURES / "v10_bad.json"
        data = json.loads(original.read_text())
        data["cases"].reverse()
        path = self.save("reversed.json", data)
        result = self.run_check(contract(path), path)
        self.assertEqual(len(result["errors"]), 4)

    def test_translated_native_write_group_preserves_both_bg_outputs(self):
        plan, path, _ = self.assembly((1, -2))
        self.assertEqual(self.run_check(plan, path)["status"], "PASS")

    def test_changed_corner_position_cannot_pass_as_same_assembly(self):
        plan, path, data = self.assembly()
        data["cases"][0]["object_x"] += 1
        path = self.save("moved.json", data)
        plan["provenance"]["candidate_trace_sha256"] = sha(path)
        result = self.run_check(plan, path)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["errors"][0]["code"], "ASSEMBLY_MISMATCH")

    def test_later_external_overlay_blocks_exact_assembly(self):
        plan, path, data = self.assembly()
        c = copy.deepcopy(next(c for c in data["cases"] if c["object_id_dec"] == 0x108))
        c["object_index"] = 6000
        c["object_layer"] = 2
        data["cases"].append(c)
        path = self.save("overlaid.json", data)
        plan["provenance"]["candidate_trace_sha256"] = sha(path)
        result = self.run_check(plan, path)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any(e["code"] == "ASSEMBLY_OVERWRITTEN" for e in result["errors"]))

    def test_unbound_changed_geometry_is_unsupported(self):
        path = FIXTURES / "v11_good.json"
        plan = contract(path)
        plan["required_object_indices"] = [84]
        result = self.run_check(plan, path)
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertEqual(result["unsupported"][0]["name"], "object[84]")

    def test_sorted_conflicting_intra_object_writes_are_unsupported(self):
        original = FIXTURES / "v11_good.json"
        data = json.loads(original.read_text())
        c = next(c for c in data["cases"] if c["object_index"] == 84)
        t = copy.deepcopy(next(t for t in c["tiles"] if (t["layer"], t["x_tile"], t["y_tile"]) == (0, 31, 39)))
        t["tile_id_dec"] += 1
        t["tile_id"] = hex(t["tile_id_dec"])
        c["tiles"].append(t)
        path = self.save("ambiguous.json", data)
        self.assertEqual(self.run_check(contract(path), path)["status"], "UNSUPPORTED")

    def test_empty_and_primitive_contracts_cannot_pass(self):
        path = FIXTURES / "v11_good.json"
        plan = contract(path)
        plan["owner_expectations"] = []
        self.assertEqual(self.run_check(plan, path)["status"], "UNSUPPORTED")
        self.assertEqual(self.run_check({"schema_version": 1, "design": {"stage": "primitive"}}, None)["status"], "UNSUPPORTED")

    def test_hash_or_mixed_state_input_is_rejected(self):
        path = FIXTURES / "v11_good.json"
        plan = contract(path)
        plan["provenance"]["candidate_trace_sha256"] = "0" * 64
        with self.assertRaisesRegex(preflight.InputError, "SHA-256 differs"):
            self.run_check(plan, path)
        data = json.loads(path.read_text())
        data["cases"][0]["state_profile"] = "alternate"
        path = self.save("mixed.json", data)
        with self.assertRaisesRegex(preflight.InputError, "mixes rooms or state"):
            self.run_check(contract(path), path)

    def test_extended_type3_ids_are_preserved(self):
        data = json.loads((FIXTURES / "v11_good.json").read_text())
        c = next(c for c in data["cases"] if c["object_index"] == 84)
        c["object_id_dec"], c["object_id"] = 0xF9B, "0xF9B"
        path = self.save("extended.json", data)
        plan = contract(path)
        plan["owner_expectations"][0]["allowed_object_ids"] = [0xF9B]
        self.assertEqual(self.run_check(plan, path)["status"], "PASS")

    def test_global_table_contact_is_unsupported_even_if_stream_overlay_wins_sort(self):
        original = FIXTURES / "v11_good.json"
        for object_id in (0x120, 0x150, 0xE00):
            with self.subTest(object_id=object_id):
                data = json.loads(original.read_text())
                # Model a table record at the corner, followed in trace index
                # order by a BG1 overlay. Actual table-pass order is omitted.
                c = copy.deepcopy(next(c for c in data["cases"] if c["object_index"] == 84))
                c.update(object_id_dec=object_id, object_id=hex(object_id), object_index=2)
                c["tiles"] = []  # Empty ordinary trace cannot clear table uncertainty.
                data["cases"].append(c)
                path = self.save(f"global-{object_id}.json", data)
                plan = contract(path)
                result = self.run_check(plan, path)
                self.assertEqual(result["status"], "UNSUPPORTED")
                self.assertEqual(len(result["unsupported"]), 1)
                plan["owner_expectations"] = plan["owner_expectations"][1:]
                self.assertEqual(self.run_check(plan, path)["status"], "PASS")

    def test_global_table_contact_cannot_certify_reference_assembly(self):
        plan, path, data = self.assembly()
        c = copy.deepcopy(next(c for c in data["cases"] if c["object_id_dec"] == 0x108))
        c.update(object_id_dec=0x120, object_id="0x120", object_index=2)
        c["tiles"] = []
        data["cases"].append(c)
        path = self.save("table-over-assembly.json", data)
        plan["provenance"]["candidate_trace_sha256"] = sha(path)
        self.assertEqual(self.run_check(plan, path)["status"], "UNSUPPORTED")

    def wall_boundary(self):
        reference = FIXTURES / "oracle25_closed_walls.json"
        data = json.loads(reference.read_text())
        path = self.save("walls.json", data)
        plan = contract(path)
        plan.update(room_id=37, owner_expectations=[], required_object_indices=list(range(40, 50)))
        plan["wall_boundaries"] = [{"name": "Oracle25 inset basin", "reference": {
            "trace": str(reference), "sha256": sha(reference), "object_indices": list(range(40, 50))},
            "candidate": {"object_indices": list(range(40, 50))}}]
        return plan, path, data

    def changed_wall_trace(self, plan, data):
        path = self.save("changed-walls.json", data)
        plan["provenance"]["candidate_trace_sha256"] = sha(path)
        return self.run_check(plan, path)

    @staticmethod
    def move_wall(c, dx, dy):
        c["object_x"] += dx
        c["object_y"] += dy
        for t in c["tiles"]:
            t["x_tile"] += dx
            t["y_tile"] += dy

    def test_captured_wall_subset_forms_cycle_without_full_room_claim(self):
        plan, path, _ = self.wall_boundary()
        result = self.run_check(plan, path)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["checked"]["wall_boundaries"], [
            {"name": "Oracle25 inset basin", "objects": 10, "joins": 10, "closed": True}])

    def test_exact_copied_corner_still_needs_wall_connectivity_evidence(self):
        plan, _, data = self.wall_boundary()
        boundary = plan.pop("wall_boundaries")[0]
        plan["required_object_indices"] = [40]
        plan["assemblies"] = [{"name": "Exact native corner copy", "reference": {
            **boundary["reference"], "object_indices": [40]},
            "candidate": {"object_indices": [40]}, "translation": [-4, -4]}]
        self.move_wall(data["cases"][0], -4, -4)
        result = self.changed_wall_trace(plan, data)
        self.assertEqual(result["checked"]["assemblies"], ["Exact native corner copy"])
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertTrue(any("no verified boundary" in e["reason"] for e in result["unsupported"]))

    def test_whole_wall_cycle_translation_remains_connected(self):
        plan, _, data = self.wall_boundary()
        for c in data["cases"]:
            self.move_wall(c, 2, 3)
        self.assertEqual(self.changed_wall_trace(plan, data)["status"], "PASS")

    def test_floating_corner_exposes_its_unconnected_faces(self):
        plan, _, data = self.wall_boundary()
        self.move_wall(data["cases"][0], -4, -4)
        result = self.changed_wall_trace(plan, data)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any(e["code"] == "WALL_UNCONNECTED_PORT" and
                            any(o["object_index"] == 40 for o in e["objects"])
                            for e in result["errors"]))

    def test_wrong_facing_native_corner_cannot_fill_same_rectangle(self):
        plan, _, data = self.wall_boundary()
        wrong = copy.deepcopy(data["cases"][1])  # Actual northeast10A at northwest108 spot.
        wrong["object_index"] = 40
        self.move_wall(wrong, -40, 0)
        data["cases"][0] = wrong
        result = self.changed_wall_trace(plan, data)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["errors"][0]["code"], "WALL_OBJECT_MISMATCH")

    def test_removed_wall_cannot_satisfy_closed_boundary(self):
        plan, _, data = self.wall_boundary()
        data["cases"] = [c for c in data["cases"] if c["object_index"] != 44]
        plan["required_object_indices"].remove(44)
        plan["wall_boundaries"][0]["candidate"]["object_indices"].remove(44)
        result = self.changed_wall_trace(plan, data)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["errors"][0]["code"], "WALL_MEMBER_COUNT")

    def test_wall_gap_and_overlap_are_reported(self):
        for dx, code in [(1, "WALL_UNCONNECTED_PORT"), (-1, "WALL_OVERLAP")]:
            with self.subTest(dx=dx):
                plan, _, data = self.wall_boundary()
                self.move_wall(next(c for c in data["cases"] if c["object_index"] == 45), dx, 0)
                result = self.changed_wall_trace(plan, data)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertTrue(any(e["code"] == code for e in result["errors"]))

    def test_open_reference_stair_mouth_needs_explicit_port_evidence(self):
        plan, _, data = self.wall_boundary()
        reference = copy.deepcopy(data)
        reference["cases"] = [c for c in reference["cases"] if c["object_index"] != 44]
        path = self.save("open-reference.json", reference)
        boundary = plan["wall_boundaries"][0]
        boundary["reference"].update(trace=str(path), sha256=sha(path))
        boundary["reference"]["object_indices"].remove(44)
        boundary["candidate"]["object_indices"].remove(44)
        plan["required_object_indices"].remove(44)
        data["cases"] = reference["cases"]
        result = self.changed_wall_trace(plan, data)
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertTrue(any("explicit port" in e["reason"] for e in result["unsupported"]))

    def add_ceiling_overlay(self, data):
        captured = json.loads((FIXTURES / "v11_good.json").read_text())
        c = copy.deepcopy(next(c for c in captured["cases"] if c["object_id_dec"] == 0xC0))
        self.move_wall(c, 9 - c["object_x"], 25 - c["object_y"])
        c.update(object_index=3000, object_layer=2, room_id=data["cases"][0]["room_id"])
        data["cases"].append(c)

    def test_closed_boundary_cannot_be_erased_by_later_ordinary_overlay(self):
        plan, _, data = self.wall_boundary()
        self.add_ceiling_overlay(data)
        result = self.changed_wall_trace(plan, data)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any(e["code"] == "WALL_OVERWRITTEN" for e in result["errors"]))

    def test_reference_overlay_context_cannot_be_dropped_for_boundary_pass(self):
        plan, _, data = self.wall_boundary()
        self.add_ceiling_overlay(data)
        ref = self.save("context-reference.json", data)
        plan["wall_boundaries"][0]["reference"].update(trace=str(ref), sha256=sha(ref))
        result = self.changed_wall_trace(plan, data)
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertTrue(any("unbound reference" in e["reason"] for e in result["unsupported"]))

    def test_disjoint_physical_backgrounds_cannot_form_one_wall_cycle(self):
        plan, _, data = self.wall_boundary()
        for i, c in enumerate(data["cases"]):
            c["tiles"] = [t for t in c["tiles"] if t["layer"] == i % 2]
        ref = self.save("disjoint-bg-reference.json", data)
        plan["wall_boundaries"][0]["reference"].update(trace=str(ref), sha256=sha(ref))
        result = self.changed_wall_trace(plan, data)
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertTrue(any("BG domain" in e["reason"] for e in result["unsupported"]))

    def test_cli_returns_nonzero_and_never_changes_inputs(self):
        for label, expected in [("v10_bad", 1), ("v11_good", 0)]:
            path = FIXTURES / f"{label}.json"
            plan_path = self.save(f"{label}-contract.json", contract(path))
            before = (sha(path), sha(plan_path))
            result = subprocess.run([sys.executable, str(SCRIPT), "--contract", str(plan_path),
                                     "--trace", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
            self.assertEqual((sha(path), sha(plan_path)), before)
        plan_path = self.save("malformed.json", {"schema_version": 1})
        result = subprocess.run([sys.executable, str(SCRIPT), "--contract", str(plan_path)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "INPUT_ERROR")


CONTACTS = FIXTURES / "contact_translator"
# (family, reference fixture, reference members, candidate fixture, candidate members)
MOUTHS = {
    "oracle_cc_spiral_wall_cut": ("oracle_cc_reference", [21, 45, 52], "oracle_cc_moved_good", [78, 79, 80]),
    "hallows_0da_south_stair_wall_cut": ("hallows_0da_reference", [56, 57], "hallows_0da_moved_good", [123, 124]),
    "alttp_61_dais_cutin_north": ("alttp_61_reference", [20, 21, 22, 23, 24, 52],
                                  "alttp_61_moved_good", [97, 98, 99, 100, 101, 102]),
}
HALLOWS = "hallows_0da_south_stair_wall_cut"


class StairMouthBoundary(unittest.TestCase):
    """Fixtures are cut from real z3ed round-trip traces (private scratch ROMs, 2026-11-08).

    Candidate cuts keep every object that writes a contact cell, so final owners
    match the full room trace."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def plan(self, family, candidate_path, candidate_ids=None, reference_path=None):
        ref_name, ref_ids, _, default_ids = MOUTHS[family]
        reference_path = reference_path or CONTACTS / f"{ref_name}.trace.json"
        data = json.loads(candidate_path.read_text())
        ids = candidate_ids or default_ids
        return {"schema_version": 1, "room_id": data["cases"][0]["room_id"],
                "state_profile": data["cases"][0]["state_profile"],
                "provenance": {"candidate_trace_sha256": sha(candidate_path)},
                "required_object_indices": list(ids), "assemblies": [], "owner_expectations": [],
                "wall_boundaries": [{"name": "mouth", "kind": "stair_mouth", "family": family,
                                     "reference": {"trace": str(reference_path), "sha256": sha(reference_path),
                                                   "object_indices": ref_ids},
                                     "candidate": {"object_indices": list(ids)}}]}

    def run_plan(self, plan, path):
        return preflight.check(plan, path, self.directory)

    def edited(self, family, edit, name="edited.json"):
        source = CONTACTS / f"{MOUTHS[family][2]}.trace.json"
        data = json.loads(source.read_text())
        edit(data)
        path = self.directory / name
        path.write_text(json.dumps(data))
        return path

    def test_round_trip_contacts_pass(self):
        for family, (_, _, candidate, ids) in MOUTHS.items():
            with self.subTest(family=family):
                path = CONTACTS / f"{candidate}.trace.json"
                result = self.run_plan(self.plan(family, path), path)
                self.assertEqual(result["status"], "PASS", result["errors"] + result["unsupported"])
                [checked] = result["checked"]["wall_boundaries"]
                self.assertEqual((checked["kind"], checked["family"], checked["objects"], checked["ends_certified"]),
                                 ("stair_mouth", family, len(ids), False))

    def test_stair_before_wall_is_blocked(self):
        path = CONTACTS / "hallows_0da_moved_wrong_order.trace.json"
        result = self.run_plan(self.plan(HALLOWS, path, [124, 123]), path)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual([e["code"] for e in result["errors"]], ["STAIR_MOUTH_ORDER"])

    def test_rotated_and_mirrored_contacts_stay_unsupported(self):
        def rotate(data):  # Transpose every member about the stair origin.
            stair = next(c for c in data["cases"] if c["object_index"] == 124)
            ax, ay = stair["object_x"], stair["object_y"]
            for c in data["cases"]:
                c["object_x"], c["object_y"] = ax + c["object_y"] - ay, ay + c["object_x"] - ax
                for t in c["tiles"]:
                    t["x_tile"], t["y_tile"] = ax + t["y_tile"] - ay, ay + t["x_tile"] - ax

        def mirror(data):
            for c in data["cases"]:
                for t in c["tiles"]:
                    t["flags"] ^= 0x4000

        for label, edit in [("rotated", rotate), ("mirrored", mirror)]:
            with self.subTest(label):
                path = self.edited(HALLOWS, edit, f"{label}.json")
                result = self.run_plan(self.plan(HALLOWS, path), path)
                self.assertEqual(result["status"], "UNSUPPORTED")
                self.assertTrue(any("rigid copy" in u["reason"] for u in result["unsupported"]))

    def test_respaced_member_is_unsupported(self):
        def shift_wall(data):
            wall = next(c for c in data["cases"] if c["object_index"] == 123)
            wall["object_x"] += 1
            for t in wall["tiles"]:
                t["x_tile"] += 1
        path = self.edited(HALLOWS, shift_wall)
        self.assertEqual(self.run_plan(self.plan(HALLOWS, path), path)["status"], "UNSUPPORTED")

    def test_later_overlay_on_mouth_is_blocked(self):
        def overlay(data):
            wall = copy.deepcopy(next(c for c in data["cases"] if c["object_index"] == 123))
            wall["object_index"] = 500
            data["cases"].append(wall)
        path = self.edited(HALLOWS, overlay)
        result = self.run_plan(self.plan(HALLOWS, path), path)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("STAIR_MOUTH_OWNER", {e["code"] for e in result["errors"]})

    def test_unmeasured_family_or_reference_is_unsupported(self):
        path = CONTACTS / "hallows_0da_moved_good.trace.json"
        plan = self.plan(HALLOWS, path)
        plan["wall_boundaries"][0]["family"] = "hallows_0da_north_stair_wall_cut"
        self.assertEqual(self.run_plan(plan, path)["status"], "UNSUPPORTED")
        # A reference with the same IDs but altered writes is not the measured contact.
        reference = json.loads((CONTACTS / "hallows_0da_reference.trace.json").read_text())
        reference["cases"][0]["tiles"][0]["tile_id_dec"] ^= 1
        reference["cases"][0]["tiles"][0]["tile_id"] = f"0x{reference['cases'][0]['tiles'][0]['tile_id_dec']:X}"
        ref_path = self.directory / "fake-reference.json"
        ref_path.write_text(json.dumps(reference))
        result = self.run_plan(self.plan(HALLOWS, path, reference_path=ref_path), path)
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertTrue(any("measured contact" in u["reason"] for u in result["unsupported"]))

    def test_malformed_family_and_shared_members_are_input_errors(self):
        path = CONTACTS / "hallows_0da_moved_good.trace.json"
        plan = self.plan(HALLOWS, path)
        plan["wall_boundaries"][0]["family"] = [HALLOWS]
        with self.assertRaises(preflight.InputError):
            self.run_plan(plan, path)
        plan = self.plan(HALLOWS, path)
        plan["wall_boundaries"].append(dict(plan["wall_boundaries"][0], name="again"))
        with self.assertRaises(preflight.InputError):
            self.run_plan(plan, path)

    def test_closed_cycle_still_rejects_stair_mouth_without_kind(self):
        path = CONTACTS / "hallows_0da_moved_good.trace.json"
        plan = self.plan(HALLOWS, path)
        del plan["wall_boundaries"][0]["kind"]
        self.assertEqual(self.run_plan(plan, path)["status"], "UNSUPPORTED")
        plan["wall_boundaries"][0]["kind"] = "open_run"
        with self.assertRaises(preflight.InputError):
            self.run_plan(plan, path)


if __name__ == "__main__":
    unittest.main()
