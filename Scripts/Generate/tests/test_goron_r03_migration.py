from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest


GENERATE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = GENERATE_DIR.parents[1]
sys.path.insert(0, str(GENERATE_DIR))

from validate_goron_r03_migration import (  # noqa: E402
    MigrationError,
    SOURCE_PATH,
    SPEC_PATH,
    digest,
    replay,
    validate_edits,
    validate_spec,
)


class GoronR03MigrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original = bytes(range(8))
        self.expected = b"\x00\xA1\xA2\x03\x04\x05\x06\x07"
        self.patch = {
            "input_sha256": digest(self.original),
            "changed_bytes": 2,
            "runs": 1,
            "edits": [{"pc": "0x000001", "before": "0102", "after": "A1A2"}],
        }
        self.target = {"size": 8, "sha256": digest(self.expected)}

    def test_repository_contract_without_rom(self) -> None:
        result = validate_spec(REPO_ROOT)
        self.assertTrue(result["passed"])
        self.assertEqual(result["explicit_zero_count"], 123)
        self.assertFalse(result["rom_replayed"])

    def test_replay_returns_exact_bytes_without_mutating_input(self) -> None:
        self.assertEqual(replay(self.original, self.patch, self.target), self.expected)
        self.assertEqual(self.original, bytes(range(8)))

    def test_replay_rejects_unknown_input_and_wrong_size(self) -> None:
        for data, message in ((b"unknown!", "Preimage SHA256"),
                              (self.original[:-1], "Preimage ROM size")):
            with self.subTest(message=message), self.assertRaisesRegex(MigrationError, message):
                replay(data, self.patch, self.target)

    def test_replay_checks_each_preimage_and_final_hash(self) -> None:
        patch = copy.deepcopy(self.patch)
        patch["edits"][0]["before"] = "FFFF"
        with self.assertRaisesRegex(MigrationError, "Edit preimage differs"):
            replay(self.original, patch, self.target)
        with self.assertRaisesRegex(MigrationError, "Reconstructed SHA256"):
            replay(self.original, self.patch, {"size": 8, "sha256": "0" * 64})

    def test_malformed_or_out_of_bounds_edits_fail_closed(self) -> None:
        cases = (
            ({"pc": "0x000001", "before": "0G", "after": "A1"}, "hex bytes"),
            ({"pc": "0x000001", "before": "01", "after": "A1A2"}, "ROM size"),
            ({"pc": "0x000007", "before": "0102", "after": "A1A2"}, "ROM size"),
            ({"pc": "0x000001", "before": "0102", "after": "01A2"}, "unchanged bytes"),
        )
        for edit, message in cases:
            with self.subTest(edit=edit), self.assertRaisesRegex(MigrationError, message):
                validate_edits({**self.patch, "edits": [edit]}, 8)

    def test_overlap_unsorted_runs_and_counts_fail_closed(self) -> None:
        for second_pc in ("0x000002", "0x000000"):
            patch = copy.deepcopy(self.patch)
            patch["edits"].append({**patch["edits"][0], "pc": second_pc})
            patch.update(runs=2, changed_bytes=4)
            with self.subTest(second_pc=second_pc), self.assertRaisesRegex(MigrationError, "overlap"):
                validate_edits(patch, 8)
        for field, value, message in (("runs", 2, "run count"),
                                      ("changed_bytes", 3, "Changed-byte count")):
            with self.subTest(field=field), self.assertRaisesRegex(MigrationError, message):
                validate_edits({**self.patch, field: value}, 8)

    def test_changed_dependency_profile_and_zero_record_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (SPEC_PATH, SOURCE_PATH, Path("Util/macros.asm"),
                             Path("Config/feature_flags.asm")):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((REPO_ROOT / relative).read_bytes())
            spec_path = root / SPEC_PATH
            original_spec = json.loads(spec_path.read_text())
            for field, replacement, message in (
                ("schema", "unknown", "schema"),
                ("source_dependency", {"pull_request": 240, "head": "0" * 40}, "dependency"),
                ("feature_profile", {**original_spec["feature_profile"], "tested_value": 0}, "profile"),
                ("application_policy", {}, "policy"),
            ):
                modified = {**original_spec, field: replacement}
                spec_path.write_text(json.dumps(modified))
                with self.subTest(field=field), self.assertRaisesRegex(MigrationError, message):
                    validate_spec(root)
            spec_path.write_text(json.dumps(original_spec))
            macro = root / "Util/macros.asm"
            macro.write_text("!ENABLE_MINECART_CART_SHUTTERS = 1\n")
            with self.assertRaisesRegex(MigrationError, "Prototype default"):
                validate_spec(root)
            macro.write_bytes((REPO_ROOT / "Util/macros.asm").read_bytes())
            source_path = root / SOURCE_PATH
            source = json.loads(source_path.read_text())
            room = next(room for room in source["rooms"] if room["room_id"] == "0x98")
            room["tiles"].remove(next(tile for tile in room["tiles"] if tile[1] == 0))
            source_path.write_text(json.dumps(source, indent=2, sort_keys=True))
            with self.assertRaisesRegex(ValueError, "SHA256"):
                validate_spec(root)


if __name__ == "__main__":
    unittest.main()
