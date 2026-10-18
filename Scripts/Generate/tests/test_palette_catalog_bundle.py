from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

GENERATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GENERATE))
from export_yazeproj_bundle import (  # noqa: E402
    _parse_project_contract,
    copy_repo_snapshot,
    validate_portable_project_contract,
    write_project_file,
)


class PaletteCatalogBundleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.bundle = self.root / "Oracle.yazeproj"
        self.bundle.mkdir()

    def stage(self, value: str | None):
        descriptor = "[files]\n"
        if value is not None:
            descriptor += f"palette_catalog_file={value}\n"
        (self.source / "Oracle-of-Secrets.yaze").write_text(descriptor)
        data = self.source / "Data/graphics/palette_catalog.json"
        data.parent.mkdir(parents=True, exist_ok=True)
        actual = GENERATE.parents[1] / "Data/graphics/palette_catalog.json"
        data.write_bytes(actual.read_bytes())
        copy_repo_snapshot(self.source, self.bundle / "project")
        return data

    def test_actual_catalog_survives_snapshot_and_relocated_descriptor(self):
        data = self.stage("Data/graphics/palette_catalog.json")
        before = hashlib.sha256(data.read_bytes()).hexdigest()
        write_project_file(self.bundle, "Oracle", "a" * 40)
        moved = self.root / "relocated" / "Renamed.yazeproj"
        moved.parent.mkdir()
        self.bundle.rename(moved)
        content = (moved / "project.yaze").read_text()
        validate_portable_project_contract(content, "a" * 40)
        _, assignments = _parse_project_contract(content)
        paths = [value for section, key, value in assignments
                 if section == "files" and key == "palette_catalog_file"]
        self.assertEqual(paths, ["project/Data/graphics/palette_catalog.json"])
        reopened_path = (moved / paths[0]).resolve()
        self.assertTrue(reopened_path.is_relative_to(moved.resolve()))
        self.assertEqual(hashlib.sha256(reopened_path.read_bytes()).hexdigest(), before)
        catalog = json.loads(reopened_path.read_text())
        self.assertEqual(catalog["schema_version"], 1)
        self.assertTrue(catalog["entries"])
        self.assertEqual(hashlib.sha256(data.read_bytes()).hexdigest(), before)
        self.assertNotIn(str(self.source), content)

    def test_invalid_catalog_refuses_before_replacing_project_file(self):
        self.stage("Data/graphics/palette_catalog.json")
        catalog_path = self.bundle / "project/Data/graphics/palette_catalog.json"
        original = json.loads(catalog_path.read_text())
        mutations = [
            ((), "schema_version", 2), ((), "schema_version", True),
            ((), "unknown", "field"), ((), "game_id", ""),
            ((), "entries", {}), ((), "entries", [{}] * 4097),
            (("entries", 0), "group", "unknown"),
            (("entries", 0), "index", 2),
            (("entries", 0), "index", -1),
            (("entries", 0), "index", 0.0),
            (("entries", 0), "index", True),
            (("entries", 0), "world", "overworld"),
            (("entries", 0), "use", "invalid"),
            (("entries", 0), "ownership", "mixed"),
            (("entries", 0), "name", "\0"),
            (("entries", 0), "name", "é" * 2049),
            (("entries", 0), "name", "\ud800"),
            (("entries", 0), "usages", {}),
            (("entries", 0), "usages", [{}] * 257),
            (("entries", 1), "key", original["entries"][0]["key"]),
            (("entries", 1), "index", 0),
            (("entries", 0, "usages", 0), "unknown", "field"),
            (("entries", 0, "usages", 0), "context", ""),
            (("entries", 0, "usages", 0), "use", "invalid"),
            (("entries", 0, "usages", 0), "obj_row", 8),
            (("entries", 0, "usages", 0), "obj_row", True),
            (("entries", 0, "usages", 0), "sprite_sheets", [108]),
            (("entries", 0, "usages", 0), "sprite_sheets", [-1]),
            (("entries", 0, "usages", 0), "sprite_sheets", [True]),
            (("entries", 0, "usages", 0), "sprite_sheets", [0] * 9),
        ]
        invalid = []
        for path, key, value in mutations:
            catalog = copy.deepcopy(original)
            target = catalog
            for component in path:
                target = target[component]
            target[key] = value
            invalid.append((str((path, key)), json.dumps(catalog).encode()))
        for path, key in [((), "schema_version"), (("entries", 0), "name"),
                          (("entries", 0, "usages", 0), "source")]:
            catalog = copy.deepcopy(original)
            target = catalog
            for component in path:
                target = target[component]
            del target[key]
            invalid.append((f"missing {key}", json.dumps(catalog).encode()))
        invalid += [("syntax", b"{"), ("encoding", b"\xff"),
                    ("too large", b" " * (1024 * 1024 + 1)),
                    ("nonfinite", b'{"schema_version":NaN}'),
                    ("root array", b"[]")]
        for label, data in invalid:
            with self.subTest(label=label):
                catalog_path.write_bytes(data)
                output = self.bundle / "project.yaze"
                output.write_text("prior descriptor\n")
                with self.assertRaises(ValueError):
                    write_project_file(self.bundle, "Oracle", "a" * 40)
                self.assertEqual(output.read_text(), "prior descriptor\n")

    def test_valid_catalog_can_grow_and_use_consumer_boundaries(self):
        self.stage("Data/graphics/palette_catalog.json")
        path = self.bundle / "project/Data/graphics/palette_catalog.json"
        catalog = json.loads(path.read_text())
        entry = copy.deepcopy(catalog["entries"][0])
        entry.update(key="additional.palette", group="sprites_aux3", index=23,
                     name="é" * 2048, world="special", use="effects")
        usage = copy.deepcopy(entry["usages"][0])
        usage.update(obj_row=7, sprite_sheets=[0, 107] * 4, use="effects")
        entry["usages"] = [usage] * 256
        catalog["entries"].append(entry)
        path.write_text(json.dumps(catalog))
        write_project_file(self.bundle, "Oracle", "a" * 40)
        self.assertIn("palette_catalog_file=project/Data/graphics/palette_catalog.json",
                      (self.bundle / "project.yaze").read_text())

    def test_all_consumer_palette_group_limits(self):
        # Yaze dec9ba7d palette_constants.h; do not import the validator's table.
        groups = {"ow_main": 6, "ow_aux": 20, "ow_animated": 14, "hud": 2,
                  "global_sprites": 2, "armors": 5, "swords": 4, "shields": 3,
                  "sprites_aux1": 12, "sprites_aux2": 11, "sprites_aux3": 24,
                  "dungeon_main": 20, "grass": 3, "3d_object": 2,
                  "ow_mini_map": 2}
        self.stage("Data/graphics/palette_catalog.json")
        path = self.bundle / "project/Data/graphics/palette_catalog.json"
        catalog = json.loads(path.read_text())
        catalog["entries"] = catalog["entries"][:1]
        for group, count in groups.items():
            with self.subTest(group=group):
                catalog["entries"][0].update(group=group, index=count - 1)
                path.write_text(json.dumps(catalog))
                write_project_file(self.bundle, "Oracle", "a" * 40)
                output = self.bundle / "project.yaze"
                before = output.read_bytes()
                catalog["entries"][0]["index"] = count
                path.write_text(json.dumps(catalog))
                with self.assertRaises(ValueError):
                    write_project_file(self.bundle, "Oracle", "a" * 40)
                self.assertEqual(output.read_bytes(), before)

    def test_unconfigured_and_empty_projects_keep_optional_key_absent(self):
        for value in (None, ""):
            with self.subTest(value=value):
                self.stage(value)
                write_project_file(self.bundle, "Oracle", "a" * 40)
                content = (self.bundle / "project.yaze").read_text()
                self.assertNotIn("palette_catalog_file=", content)
                validate_portable_project_contract(content, "a" * 40)

    def test_bad_paths_refuse_before_replacing_project_file(self):
        for value in ("/outside.json", "../outside.json", "C:\\outside.json",
                      "Data/missing.json", "project/../Data/catalog.json"):
            with self.subTest(value=value):
                self.stage(value)
                output = self.bundle / "project.yaze"
                output.write_text("prior descriptor\n")
                with self.assertRaises((ValueError, FileNotFoundError)):
                    write_project_file(self.bundle, "Oracle", "a" * 40)
                self.assertEqual(output.read_text(), "prior descriptor\n")

    def test_symlink_escape_and_duplicate_setting_refuse(self):
        self.stage("escape.json")
        outside = self.bundle / "outside.json"
        outside.write_text("{}")
        (self.bundle / "project/escape.json").symlink_to(outside)
        with self.assertRaises(ValueError):
            write_project_file(self.bundle, "Oracle", "a" * 40)
        (self.bundle / "project/Oracle-of-Secrets.yaze").write_text(
            "[files]\npalette_catalog_file=first.json\n"
            "palette_catalog_file=second.json\n")
        with self.assertRaises(ValueError):
            write_project_file(self.bundle, "Oracle", "a" * 40)


if __name__ == "__main__":
    unittest.main()
