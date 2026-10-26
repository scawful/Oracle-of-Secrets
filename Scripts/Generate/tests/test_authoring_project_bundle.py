from __future__ import annotations

import hashlib
import json
import shutil
import sys
import unittest
from pathlib import Path

GENERATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GENERATE))

from export_yazeproj_bundle import (  # noqa: E402
    _parse_project_contract,
    copy_repo_snapshot,
    verify_bundle,
    write_authoring_project,
    write_bundle_hack_manifest,
)
import test_generate_hack_manifest as manifest_tests  # noqa: E402


class AuthoringProjectBundleTest(unittest.TestCase):
    def setUp(self):
        self.base = manifest_tests.PortableBundleManifestTest(
            "test_manifest_uses_one_bundle_root_namespace_after_relocation"
        )
        self.base.setUp()
        self.addCleanup(self.base.tearDown)
        self.bundle = self.base.bundle_root.resolve()
        self.root = self.base.fixture.root.resolve()
        self.source = self.root / "working"
        self.source.mkdir()
        self.project = self.source / "Working.yaze"
        self.project.write_text("""# User comment
[project]
name=User Authoring Project
project_id=retain-user-identity
[files]
rom_filename=old.sfc
lyra_terrain_file=terrain.json
dungeon_tile_patterns=walls.asm
custom_collision_json=collision.json
custom_objects_folder=objects
hack_manifest_file=hack_manifest.json
overworld_graphics_preview=graphics/catalog.json
[rom]
role=dev
expected_hash=old
write_policy=block
[feature_flags]
save_dungeon_maps=false
save_dungeon_water_fill_zones=false
save_graphics_sheet=true
save_gfx_groups=true
[workspace]
autosave_enabled=false
backup_on_save=true
recent_files=/external/user/project.yaze
[build]
build_script=/external/run.sh
git_repository=/external/source
asm_sources=/external/main.asm
[graphics_sheets]
reserved_sheets=0x7B,0x7C
flagged_sheets=0xD4,0xD6
[labels_room]
151=My Goron Room
""")
        self.write("terrain.json", b'{"populated":"sidecar","cells":[1,2,3]}')
        self.write("walls.asm", b"WallPattern:\n dw $1234\n")
        self.write("collision.json", b'{"rooms":{"151":[1,2]}}')
        self.write("objects/001.bin", b"custom object bytes")
        self.write("tracks.asm", b"; preserved authored cart source\n")
        self.write(
            "hack_manifest.json",
            json.dumps(
                {"minecart_tracks": {"source": {"path": "tracks.asm"}}}
            ).encode(),
        )
        self.write(
            "graphics/catalog.json",
            json.dumps(
                {
                    "schema_version": 2,
                    "resources": {"entrance": {"path": "pages/entrance.bin"}},
                    "bindings": [{"parent_maps": [135], "profile_id": "tower"}],
                }
            ).encode(),
        )
        self.write("graphics/pages/entrance.bin", bytes(range(64)))
        self.rom_sha1 = hashlib.sha1((self.bundle / "rom").read_bytes()).hexdigest()

    def write(self, relative, data):
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def capture(self, **kwargs):
        write_authoring_project(
            self.bundle, self.project, self.rom_sha1, desktop=True, **kwargs
        )
        write_bundle_hack_manifest(self.bundle)

    def values(self):
        _, assignments = _parse_project_contract(
            (self.bundle / "project.yaze").read_text()
        )
        return {(section, key): value for section, key, value in assignments}

    def run_main(self, output, *, authoring=True, force=False):
        from unittest import mock
        import export_yazeproj_bundle as exporter

        args = [
            "export_yazeproj_bundle.py",
            "--rom",
            str(self.bundle / "rom"),
            "--out",
            str(output),
        ]
        if authoring:
            args += ["--project", str(self.project), "--desktop"]
        if force:
            args += ["--force"]
        with (
            mock.patch.object(
                exporter, "find_repo_root", return_value=self.base.project_root
            ),
            mock.patch.object(sys, "argv", args),
        ):
            return exporter.main()

    def test_preserves_identity_labels_flags_and_exact_resource_bytes(self):
        before = {
            p.relative_to(self.source): p.read_bytes()
            for p in self.source.rglob("*")
            if p.is_file()
        }
        rom_before = (self.bundle / "rom").read_bytes()
        self.capture()
        verify_bundle(self.bundle)
        values = self.values()
        self.assertEqual(values["project", "project_id"], "retain-user-identity")
        self.assertEqual(values["project", "name"], "User Authoring Project")
        self.assertEqual(values["labels_room", "151"], "My Goron Room")
        self.assertEqual(values["feature_flags", "save_graphics_sheet"], "true")
        self.assertEqual(values["feature_flags", "save_gfx_groups"], "true")
        self.assertIn("# User comment", (self.bundle / "project.yaze").read_text())
        self.assertEqual(
            (self.bundle / values["files", "lyra_terrain_file"]).read_bytes(),
            before[Path("terrain.json")],
        )
        self.assertEqual(
            (self.bundle / "assets/graphics-preview/pages/entrance.bin").read_bytes(),
            before[Path("graphics/pages/entrance.bin")],
        )
        self.assertEqual(
            (self.bundle / "project/Dungeons/Objects/Data/001.bin").read_bytes(),
            before[Path("objects/001.bin")],
        )
        self.assertEqual(
            (
                self.bundle / "project/Sprites/Objects/data/minecart_tracks.asm"
            ).read_bytes(),
            before[Path("tracks.asm")],
        )
        self.assertEqual((self.bundle / "rom").read_bytes(), rom_before)
        self.assertEqual(values["workspace", "recent_files"], "")
        self.assertNotIn("/external/", (self.bundle / "project.yaze").read_text())
        self.assertEqual(
            before,
            {
                p.relative_to(self.source): p.read_bytes()
                for p in self.source.rglob("*")
                if p.is_file()
            },
        )

    def test_explicit_overrides_replace_missing_original_bindings(self):
        (self.source / "terrain.json").unlink()
        shutil.rmtree(self.source / "graphics")
        terrain = self.write("override/populated.json", b'{"maps":[160,191]}')
        preview = self.write(
            "override/catalog.json", b'{"areas":[{"transfers":[{"path":"new.bin"}]}]}'
        )
        art = self.write("override/new.bin", b"new art")
        self.capture(lyra_terrain=terrain, graphics_preview=preview)
        verify_bundle(self.bundle)
        self.assertEqual(
            (self.bundle / self.values()["files", "lyra_terrain_file"]).read_bytes(),
            terrain.read_bytes(),
        )
        self.assertEqual(
            (self.bundle / "assets/graphics-preview/new.bin").read_bytes(),
            art.read_bytes(),
        )

    def test_relocated_bundle_has_no_external_active_bindings(self):
        self.capture()
        relocated = self.root / "relocated" / "Renamed.yazeproj"
        relocated.parent.mkdir()
        self.bundle.rename(relocated)
        verify_bundle(relocated)
        self.assertNotIn(str(self.source), (relocated / "project.yaze").read_text())

    def test_missing_dependency_refuses_before_descriptor_replacement(self):
        original = (self.bundle / "project.yaze").read_bytes()
        (self.source / "walls.asm").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "Missing dependency"):
            self.capture()
        self.assertEqual((self.bundle / "project.yaze").read_bytes(), original)

    def test_desktop_mode_is_explicit_not_silently_portable(self):
        with self.assertRaisesRegex(ValueError, "save_graphics_sheet"):
            write_authoring_project(self.bundle, self.project, self.rom_sha1)

    def test_symlink_file_and_directory_refused(self):
        original = (self.source / "terrain.json").read_bytes()
        target = self.write("real-terrain.json", original)
        (self.source / "terrain.json").unlink()
        (self.source / "terrain.json").symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.capture()
        (self.source / "terrain.json").unlink()
        self.write("terrain.json", original)
        (self.source / "objects/alias").symlink_to(
            self.source / "graphics", target_is_directory=True
        )
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.capture()

    def test_graphics_path_escape_and_missing_resource_refused(self):
        for path in (
            "../terrain.json",
            str(self.source / "terrain.json"),
            "missing.bin",
        ):
            with self.subTest(path=path):
                self.write(
                    "graphics/catalog.json",
                    json.dumps({"resources": {"x": {"path": path}}}).encode(),
                )
                with self.assertRaises((ValueError, FileNotFoundError)):
                    self.capture()

    def test_resource_tamper_fails_bundle_readback(self):
        self.capture()
        (self.bundle / "assets/graphics-preview/pages/entrance.bin").write_bytes(
            b"tampered"
        )
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            verify_bundle(self.bundle)

    def test_descriptor_retarget_fails_bundle_readback(self):
        self.capture()
        path = self.bundle / "project.yaze"
        path.write_text(
            path.read_text().replace(
                "lyra_terrain_file=assets/", "lyra_terrain_file=/outside/"
            )
        )
        with self.assertRaisesRegex(ValueError, "descriptor differs"):
            verify_bundle(self.bundle)

    def test_snapshot_symlinks_and_recursive_output_refused(self):
        source = self.root / "mini-source"
        source.mkdir()
        (source / "linked").symlink_to(self.source / "terrain.json")
        with self.assertRaisesRegex(ValueError, "symlink"):
            copy_repo_snapshot(source, self.root / "snapshot", reject_symlinks=True)
        with self.assertRaisesRegex(ValueError, "inside captured source"):
            copy_repo_snapshot(source, source / "nested", reject_symlinks=True)

    def test_planning_and_atlas_writes_resolve_inside_bundle(self):
        self.write("plan.json", b'{"schema":"yaze.plan/1"}')
        self.write("annotations.json", b'{"annotations":[]}')
        with self.project.open("a") as stream:
            stream.write(
                "\n[planning]\nfile=plan.json\n[atlas]\nannotations=annotations.json\nexport_folder=/external/exports\n"
            )
        self.capture()
        verify_bundle(self.bundle)
        values = self.values()
        self.assertEqual(values["atlas", "export_folder"], "output/atlas")
        self.assertTrue((self.bundle / values["planning", "file"]).is_file())
        self.assertTrue((self.bundle / values["atlas", "annotations"]).is_file())

    def test_source_change_during_capture_refuses_publication(self):
        from unittest import mock

        original = (self.bundle / "project.yaze").read_bytes()
        real_validate = __import__(
            "export_yazeproj_bundle"
        ).validate_portable_project_contract

        def change_source(*args, **kwargs):
            (self.source / "terrain.json").write_bytes(b"changed concurrently")
            return real_validate(*args, **kwargs)

        with mock.patch(
            "export_yazeproj_bundle.validate_portable_project_contract",
            side_effect=change_source,
        ):
            with self.assertRaisesRegex(ValueError, "changed during capture"):
                self.capture()
        self.assertEqual((self.bundle / "project.yaze").read_bytes(), original)

    def test_graphics_catalog_declared_hash_is_enforced(self):
        self.write(
            "graphics/catalog.json",
            json.dumps(
                {
                    "resources": {
                        "x": {
                            "path": "pages/entrance.bin",
                            "sha256": "0" * 64,
                            "byte_count": 64,
                        }
                    }
                }
            ).encode(),
        )
        with self.assertRaisesRegex(ValueError, "resource hash mismatch"):
            self.capture()

    def test_main_materializes_only_a_new_synthetic_output(self):
        from unittest import mock
        import export_yazeproj_bundle as exporter

        output = self.root / "fresh" / "Authoring.yazeproj"
        args = [
            "export_yazeproj_bundle.py",
            "--project",
            str(self.project),
            "--rom",
            str(self.bundle / "rom"),
            "--desktop",
            "--out",
            str(output),
        ]
        with (
            mock.patch.object(
                exporter, "find_repo_root", return_value=self.base.project_root
            ),
            mock.patch.object(sys, "argv", args),
        ):
            self.assertEqual(exporter.main(), 0)
        verify_bundle(output)
        before = (output / "project.yaze").read_bytes()
        with (
            mock.patch.object(
                exporter, "find_repo_root", return_value=self.base.project_root
            ),
            mock.patch.object(sys, "argv", args + ["--force"]),
        ):
            with self.assertRaisesRegex(ValueError, "fresh output"):
                exporter.main()
        self.assertEqual((output / "project.yaze").read_bytes(), before)

    def test_rom_drift_after_verification_refuses_final_publication(self):
        from unittest import mock
        import export_yazeproj_bundle as exporter

        output = self.root / "late-rom" / "Authoring.yazeproj"
        selected = self.bundle / "rom"
        before = selected.read_bytes()

        def mutate_after_verification(path):
            verify_bundle(path)
            selected.write_bytes(before[:-1] + bytes([before[-1] ^ 1]))

        with mock.patch.object(
            exporter, "verify_bundle", side_effect=mutate_after_verification
        ):
            with self.assertRaisesRegex(
                ValueError, "changed before authoring publication"
            ):
                self.run_main(output)
        self.assertFalse(output.exists())
        staging = output.with_name(output.name + ".staging")
        self.assertEqual((staging / "rom").read_bytes(), before)

    def test_empty_output_appearing_at_rename_is_not_replaced(self):
        from unittest import mock
        import export_yazeproj_bundle as exporter

        output = self.root / "late-output" / "Authoring.yazeproj"
        original_rename = exporter._rename_without_replacement
        occupied_inode = []

        def occupy_then_rename(source, destination):
            destination.mkdir()
            occupied_inode.append(destination.stat().st_ino)
            original_rename(source, destination)

        with mock.patch.object(
            exporter, "_rename_without_replacement", side_effect=occupy_then_rename
        ):
            with self.assertRaises(FileExistsError):
                self.run_main(output)
        self.assertEqual(output.stat().st_ino, occupied_inode[0])
        self.assertEqual(list(output.iterdir()), [])
        self.assertTrue(output.with_name(output.name + ".staging").is_dir())

    def test_old_path_appearing_after_verification_is_preserved(self):
        from unittest import mock
        import export_yazeproj_bundle as exporter

        output = self.root / "late-old" / "Authoring.yazeproj"
        old = output.with_name(output.name + ".old")

        def occupy_after_verification(path):
            verify_bundle(path)
            old.mkdir()
            (old / "owner.txt").write_text("foreign directory")

        with mock.patch.object(
            exporter, "verify_bundle", side_effect=occupy_after_verification
        ):
            with self.assertRaisesRegex(FileExistsError, "old path became occupied"):
                self.run_main(output)
        self.assertFalse(output.exists())
        self.assertEqual((old / "owner.txt").read_text(), "foreign directory")
        self.assertTrue(output.with_name(output.name + ".staging").is_dir())

    def test_default_portable_force_still_replaces_its_output(self):
        output = self.root / "portable" / "Oracle.yazeproj"
        self.assertEqual(self.run_main(output, authoring=False), 0)
        (output / "previous-output.txt").write_text("replace me")
        old = output.with_name(output.name + ".old")
        old.mkdir()
        (old / "previous-backup.txt").write_text("legacy replacement")
        self.assertEqual(self.run_main(output, authoring=False, force=True), 0)
        verify_bundle(output)
        self.assertFalse((output / "previous-output.txt").exists())
        self.assertFalse(old.exists())


if __name__ == "__main__":
    unittest.main()
