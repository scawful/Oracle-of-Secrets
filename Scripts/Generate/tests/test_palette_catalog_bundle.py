from __future__ import annotations

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
        self.assertEqual(len(catalog["entries"]), 8)
        self.assertEqual(hashlib.sha256(data.read_bytes()).hexdigest(), before)
        self.assertNotIn(str(self.source), content)

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
