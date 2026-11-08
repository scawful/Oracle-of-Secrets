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

    def test_actual_oracle25_wall_surround_is_one_closed_cycle(self):
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


if __name__ == "__main__":
    unittest.main()
