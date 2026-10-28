from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import unittest
from pathlib import Path

GENERATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GENERATE))

from export_yazeproj_bundle import (  # noqa: E402
    AUTHORING_BUILD_COMMAND,
    AUTHORING_BUILD_SCRIPT,
    PORTABLE_BUILD_COMMAND,
    _parse_project_contract,
    copy_repo_snapshot,
    verify_bundle,
    write_authoring_project,
    write_bundle_hack_manifest,
)
import test_generate_hack_manifest as manifest_tests  # noqa: E402

sys.path.insert(0, str(GENERATE.parent / "Build"))
import authoring_bundle_build as build_guard  # noqa: E402


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

    def test_planning_stays_live_and_atlas_writes_resolve_inside_bundle(self):
        # Planning is a declared live project reference, not build input: the
        # export keeps the plan in place and records no provenance for it.
        plan = self.write("plan.json", b'{"schema":"yaze.plan/1"}')
        self.write("annotations.json", b'{"annotations":[]}')
        with self.project.open("a") as stream:
            stream.write(
                "\n[planning]\nfile=plan.json\n[atlas]\nannotations=annotations.json\nexport_folder=/external/exports\n"
            )
        self.capture()
        verify_bundle(self.bundle)
        values = self.values()
        self.assertEqual(values["atlas", "export_folder"], "output/atlas")
        self.assertEqual(values["planning", "file"], str(plan.resolve()))
        self.assertTrue((self.bundle / values["atlas", "annotations"]).is_file())
        receipt = json.loads((self.bundle / "authoring-dependencies.json").read_text())
        self.assertNotIn("planning.file", receipt["bindings"])
        self.assertFalse(any("plan.json" in name for name in receipt["files"]))
        plan.write_bytes(b'{"schema":"yaze.plan/1","status":"agent edit"}')
        verify_bundle(self.bundle)

    def test_planning_that_aliases_a_build_input_refuses_export(self):
        with self.project.open("a") as stream:
            stream.write("\n[planning]\nfile=walls.asm\n")
        with self.assertRaisesRegex(ValueError, "planning.file .* is also a ROM/tool/build input"):
            self.capture()

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
        _, assignments = _parse_project_contract((output / "project.yaze").read_text())
        self.assertIn(("build", "build_script", PORTABLE_BUILD_COMMAND), assignments)
        self.assertFalse((output / "previous-output.txt").exists())
        self.assertFalse(old.exists())

    def test_authoring_build_refuses_lyra_before_any_delegate_or_write(self):
        import contextlib
        import io
        from unittest import mock

        self.write(
            "terrain.json",
            json.dumps(
                {
                    "schema_version": 4,
                    "maps": [
                        {"id": 160, "tiles": [[1]], "background_palette": [0] * 128}
                    ],
                }
            ).encode(),
        )
        self.capture()
        self.assertEqual(
            self.values()["build", "build_script"], AUTHORING_BUILD_COMMAND
        )
        self.assertTrue((self.bundle / AUTHORING_BUILD_SCRIPT).is_file())
        output = self.bundle / "project/Roms/oos168x.sfc"
        output.write_bytes(b"previous output")
        before = {
            p.relative_to(self.bundle): p.read_bytes()
            for p in self.bundle.rglob("*")
            if p.is_file()
        }
        error = io.StringIO()
        with (
            mock.patch.object(build_guard.subprocess, "run") as delegate,
            contextlib.redirect_stderr(error),
        ):
            self.assertEqual(
                build_guard.main(["--project", str(self.bundle / "project.yaze")]), 2
            )
        delegate.assert_not_called()
        self.assertIn("lyra_build_request_file", error.getvalue())
        self.assertIn("No build was started", error.getvalue())
        self.assertEqual(
            before,
            {
                p.relative_to(self.bundle): p.read_bytes()
                for p in self.bundle.rglob("*")
                if p.is_file()
            },
        )

    def test_authoring_build_empty_or_absent_binding_delegates_native(self):
        from unittest import mock

        original = self.project.read_text()
        for replacement in ("lyra_terrain_file=\n", ""):
            with self.subTest(binding=replacement):
                self.project.write_text(
                    original.replace("lyra_terrain_file=terrain.json\n", replacement)
                )
                self.capture()
                with mock.patch.object(
                    build_guard.subprocess, "run", return_value=mock.Mock(returncode=7)
                ) as delegate:
                    self.assertEqual(
                        build_guard.main(
                            ["--project", str(self.bundle / "project.yaze")]
                        ),
                        7,
                    )
                args, kwargs = delegate.call_args
                self.assertEqual(
                    args[0],
                    [
                        "bash",
                        str(self.bundle / "project/Scripts/Build/build_rom.sh"),
                        "168",
                    ],
                )
                self.assertEqual(kwargs["cwd"], self.bundle)
                self.assertEqual(kwargs["env"]["OOS_BASE_ROM"], "rom")
                self.assertEqual(kwargs["env"]["OOS_BACKUP_ROOT"], "backups")
                self.assertEqual(kwargs["env"]["OOS_MANIFEST_ROOT"], ".")

    def test_export_preserves_supported_build_refs_without_rewriting_save_identity(self):
        controls = ('lyra_build_request_file', 'native_save_receipt_file',
                    'native_save_producer_file', 'native_save_transfer_proof_file')
        content = self.project.read_text()
        for key in controls:
            self.write(key + '.json', json.dumps({'original_project':str(self.project),'field':key}).encode())
            content = content.replace('[files]\n','[files]\n'+key+'='+key+'.json\n',1)
        self.project.write_text(content)
        self.capture();verify_bundle(self.bundle)
        values = self.values()
        for key in controls:
            captured = self.bundle / values['files',key]
            self.assertEqual(captured.read_bytes(),(self.source / (key+'.json')).read_bytes())
            self.assertIn(str(self.project),captured.read_text())
        # A relocated descriptor cannot borrow the original Save/context.
        self.assertFalse(Path(str(self.bundle/'project.yaze')+'.native-save.json').exists())

    def test_native_build_discards_inherited_foreign_current_selection(self):
        from unittest import mock
        self.project.write_text(self.project.read_text().replace('lyra_terrain_file=terrain.json','lyra_terrain_file='))
        self.capture()
        foreign={key:'/foreign/project' for key in
                 ('OOS_LYRA_PROJECT','OOS_LYRA_REQUEST','OOS_LYRA_CANDIDATE','OOS_LYRA_BUILD_CONTEXT')}
        with mock.patch.dict(build_guard.os.environ,foreign),mock.patch.object(
                build_guard.subprocess,'run',return_value=mock.Mock(returncode=0)) as delegate:
            self.assertEqual(build_guard.build_project(self.bundle/'project.yaze'),0)
        for key in foreign:self.assertNotIn(key,delegate.call_args.kwargs['env'])

    def pin_tools(self):
        """Export provenance as staged for a desktop bundle with pinned tools."""
        self.producer = self.root / "Pinned.app/Contents/MacOS/yaze"
        self.producer.parent.mkdir(parents=True, exist_ok=True)
        self.producer.write_bytes(b"pinned producer executable")
        pinned = {
            "app_executable": "yaze.app/Contents/MacOS/yaze",
            "app_executable_sha256": hashlib.sha256(
                self.producer.read_bytes()).hexdigest(),
        }
        receipt_path = self.bundle / "authoring-dependencies.json"
        receipt = json.loads(receipt_path.read_text())
        for relative, data in (
            ("tools/producer.json", json.dumps(pinned).encode()),
            ("tools/z3ed", b"pinned cli"),
        ):
            path = self.bundle / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            receipt["files"][relative] = {
                "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    def saved_terrain_edit(self):
        """Bytes a project Save writes: the terrain sidecar and the descriptor."""
        self.capture()
        self.pin_tools()
        self.export_receipt = (self.bundle / "authoring-dependencies.json").read_bytes()
        self.terrain = self.bundle / self.values()["files", "lyra_terrain_file"]
        self.terrain.write_bytes(b'{"populated":"sidecar","cells":[1,2,4]}')
        descriptor = self.bundle / "project.yaze"
        descriptor.write_text(descriptor.read_text().replace(
            "[labels_room]\n151=My Goron Room", "[labels_room]\n151=Saved Goron Room"))

    def write_native_save(self, *, errors=(), producer=None, **artifact_paths):
        bound = {"rom": self.bundle / "rom", "producer": producer or self.producer,
                 "project": self.bundle / "project.yaze", "sidecar": self.terrain}
        bound.update(artifact_paths)
        receipt = self.bundle / "project.yaze.native-save.json"
        artifacts = []
        for role, path in sorted(bound.items()):
            data = path.read_bytes()
            artifacts.append({"role": role, "path": str(path.resolve()),
                              "sha256": hashlib.sha256(data).hexdigest(),
                              "bytes": len(data)})
        receipt.write_text(json.dumps({
            "kind": "yaze.native_save.v1", "generation": 3,
            "operation_id": "0123abcd4567ef890123abcd4567ef89", "operation": "save",
            "receipt_path": str(receipt.resolve()),
            "bindings_complete": not errors, "binding_errors": list(errors),
            "artifacts": artifacts}, indent=2) + "\n")
        return receipt

    def test_native_saved_terrain_and_descriptor_pass_without_rewriting_provenance(self):
        self.saved_terrain_edit()
        self.write_native_save()
        verify_bundle(self.bundle)
        self.write_native_save(
            errors=["dependency.sprite_0_source: imported source is stale"])
        verify_bundle(self.bundle)
        self.assertEqual(
            (self.bundle / "authoring-dependencies.json").read_bytes(),
            self.export_receipt)

    def test_external_edit_without_native_save_receipt_refuses(self):
        self.capture()
        self.pin_tools()
        terrain = self.bundle / self.values()["files", "lyra_terrain_file"]
        terrain.write_bytes(b'{"edited":"outside yaze"}')
        with self.assertRaisesRegex(
                ValueError, "hash mismatch: assets/project/lyra_terrain_file/"
                "terrain.json changed and no project.yaze.native-save.json"):
            verify_bundle(self.bundle)
        self.saved_terrain_edit()
        with self.assertRaisesRegex(ValueError, "descriptor differs.*external"):
            verify_bundle(self.bundle)

    def test_edit_after_native_save_refuses(self):
        self.saved_terrain_edit()
        self.write_native_save()
        self.terrain.write_bytes(b'{"edited":"after save"}')
        with self.assertRaisesRegex(
                ValueError, "does not bind current assets/project/lyra_terrain_file/"
                r"terrain.json \(role sidecar\)"):
            verify_bundle(self.bundle)
        self.write_native_save()
        descriptor = self.bundle / "project.yaze"
        descriptor.write_text(descriptor.read_text() + "# appended later\n")
        with self.assertRaisesRegex(ValueError, r"current project.yaze \(role project\)"):
            verify_bundle(self.bundle)

    def test_changed_immutable_file_refuses_despite_native_save(self):
        self.saved_terrain_edit()
        for relative in ("tools/z3ed", "assets/project/dungeon_tile_patterns/walls.asm"):
            with self.subTest(relative=relative):
                path = self.bundle / relative
                original = path.read_bytes()
                path.write_bytes(original + b"\n; tampered")
                self.write_native_save(
                    **{"dependency.dungeon_tile_patterns": path}
                    if relative.endswith(".asm") else {})
                with self.assertRaisesRegex(
                        ValueError, f"hash mismatch: {relative} is immutable"):
                    verify_bundle(self.bundle)
                path.write_bytes(original)

    def test_native_save_producer_mismatch_refuses(self):
        self.saved_terrain_edit()
        other = self.root / "Other.app/Contents/MacOS/yaze"
        other.parent.mkdir(parents=True)
        other.write_bytes(b"unpinned producer")
        self.write_native_save(producer=other)
        with self.assertRaisesRegex(ValueError, "not the bundle's pinned tools app"):
            verify_bundle(self.bundle)

    def test_native_save_binding_errors_on_changed_role_refuse(self):
        self.saved_terrain_edit()
        for error in ("Saved terrain differs from the live document",
                      "sidecar: Cannot read native save input",
                      "project: unreadable", "2 additional binding errors"):
            with self.subTest(error=error):
                self.write_native_save(errors=[error])
                with self.assertRaisesRegex(ValueError, "incomplete Save binding"):
                    verify_bundle(self.bundle)

    def test_relabeled_or_malformed_native_save_receipt_refuses(self):
        self.saved_terrain_edit()
        receipt = self.write_native_save()
        good = json.loads(receipt.read_text())
        for field, value in (("receipt_path", "/elsewhere/project.yaze.native-save.json"),
                             ("kind", "yaze.native_save.v0"), ("generation", 0),
                             ("operation", "export"), ("bindings_complete", False)):
            with self.subTest(field=field):
                receipt.write_text(json.dumps({**good, field: value}))
                with self.assertRaisesRegex(ValueError, "Invalid native-save receipt"):
                    verify_bundle(self.bundle)
        receipt.write_text(json.dumps(
            {**good, "artifacts": [a for a in good["artifacts"] if a["role"] != "rom"]}))
        with self.assertRaisesRegex(ValueError, "rom and producer roles"):
            verify_bundle(self.bundle)

    def test_native_saved_descriptor_cannot_add_external_binding(self):
        self.saved_terrain_edit()
        descriptor = self.bundle / "project.yaze"
        saved = descriptor.read_text()
        descriptor.write_text(saved + "\n[atlas]\nsymbols=/external/oracle.sym\n")
        self.write_native_save()
        with self.assertRaisesRegex(ValueError, "binds atlas.symbols outside the bundle"):
            verify_bundle(self.bundle)

    def test_native_saved_live_planning_reference_passes_outside_bundle(self):
        self.saved_terrain_edit()
        plan = self.root / "afs/oracle.plan.json"
        plan.parent.mkdir()
        plan.write_bytes(b'{"schema":"yaze.plan/1"}')
        descriptor = self.bundle / "project.yaze"
        descriptor.write_text(descriptor.read_text() + f"\n[planning]\nfile={plan}\n")
        self.write_native_save()
        verify_bundle(self.bundle)
        plan.write_bytes(b'{"schema":"yaze.plan/1","status":"agent edit"}')
        verify_bundle(self.bundle)
        self.assertEqual(
            (self.bundle / "authoring-dependencies.json").read_bytes(),
            self.export_receipt)

    def test_live_planning_that_aliases_a_build_or_save_input_refuses(self):
        self.saved_terrain_edit()
        descriptor = self.bundle / "project.yaze"
        saved = descriptor.read_text()
        outside = self.root / "labels.json"
        outside.write_bytes(b"{}")
        for target in ("tools/z3ed", "rom", "project/Oracle_main.asm",
                       "assets/project/lyra_terrain_file/terrain.json", str(outside)):
            with self.subTest(target=target):
                descriptor.write_text(saved + f"\n[planning]\nfile={target}\n")
                extra = ({"dependency.labels_filename": outside}
                         if target == str(outside) else {})
                self.write_native_save(**extra)
                with self.assertRaisesRegex(
                        ValueError, "planning.file .* is also a ROM/tool/build input"):
                    verify_bundle(self.bundle)

    def test_old_receipt_binding_live_planning_requires_a_new_save(self):
        self.saved_terrain_edit()
        plan = self.root / "oracle.plan.json"
        plan.write_bytes(b'{"schema":"yaze.plan/1"}')
        self.write_native_save(**{"dependency.planning": plan})
        with self.assertRaisesRegex(
                ValueError, "binds dependency.planning.*new native Save"):
            verify_bundle(self.bundle)
        self.write_native_save()
        verify_bundle(self.bundle)

    def test_mandatory_role_binding_errors_refuse_even_when_hashes_match(self):
        self.saved_terrain_edit()
        for error in ("rom: explicit incomplete binding",
                      "producer: explicit incomplete binding"):
            with self.subTest(error=error):
                self.write_native_save(errors=[error])
                with self.assertRaisesRegex(
                        ValueError, f"incomplete Save binding.*{error}"):
                    verify_bundle(self.bundle)

    def saved_build_target(self, target):
        """A project-only Save that names a new output; returns the descriptor."""
        self.saved_terrain_edit()
        descriptor = self.bundle / "project.yaze"
        descriptor.write_text(descriptor.read_text().replace(
            "build_target=project/Roms/oos168x.sfc", f"build_target={target}"))
        return descriptor

    def test_native_saved_build_target_passes_as_output_metadata(self):
        target = self.root / "engine/Roms/generation-01/oos168x.sfc"
        self.saved_build_target(target)
        self.write_native_save()
        verify_bundle(self.bundle)
        self.assertEqual(self.values()["build", "build_target"], str(target))
        self.assertEqual(
            (self.bundle / "authoring-dependencies.json").read_bytes(),
            self.export_receipt)
        self.assertFalse(target.parent.exists())

    def test_build_target_change_without_a_current_complete_save_refuses(self):
        target = self.root / "engine/Roms/generation-01/oos168x.sfc"
        descriptor = self.saved_build_target(target)
        with self.assertRaisesRegex(ValueError, "descriptor differs.*external"):
            verify_bundle(self.bundle)
        saved = descriptor.read_text()
        descriptor.write_text(saved.replace(str(target), "project/Roms/oos168x.sfc"))
        self.write_native_save()
        descriptor.write_text(saved)
        with self.assertRaisesRegex(ValueError, r"current project.yaze \(role project\)"):
            verify_bundle(self.bundle)
        self.write_native_save(
            errors=["dependency.sprite_0_source: imported source is stale"])
        with self.assertRaisesRegex(ValueError, "build_target .* not bound by a complete"):
            verify_bundle(self.bundle)
        self.write_native_save(errors=["project: unreadable"])
        with self.assertRaisesRegex(ValueError, "incomplete Save binding"):
            verify_bundle(self.bundle)

    def test_saved_build_target_that_aliases_an_input_refuses(self):
        outside = self.root / "labels.sfc"
        outside.write_bytes(b"{}")
        linked = self.root / "linked.sfc"
        linked.symlink_to(self.bundle / "rom")
        hardlinked = self.root / "hardlinked.sfc"
        os.link(self.bundle / "rom", hardlinked)
        plan = self.root / "plan.sfc"
        plan.write_text("{}")
        hardlinked_plan = self.root / "hardlinked-plan.sfc"
        os.link(plan, hardlinked_plan)
        for target in ("rom", "project.yaze", "tools/z3ed", "project/Oracle_main.sfc",
                       "assets/project/output.sfc", str(outside), str(linked),
                       str(hardlinked), str(plan), str(hardlinked_plan), str(self.root / "dir.sfc")):
            with self.subTest(target=target):
                descriptor = self.saved_build_target(target)
                if target in (str(plan), str(hardlinked_plan)):
                    descriptor.write_text(
                        descriptor.read_text() + f"\n[planning]\nfile={plan}\n")
                if target.endswith("dir.sfc"):
                    Path(target).mkdir(exist_ok=True)
                extra = ({"dependency.labels_filename": outside}
                         if target == str(outside) else {})
                self.write_native_save(**extra)
                with self.assertRaisesRegex(
                        ValueError, f"build_target {re.escape(target)} aliases"):
                    verify_bundle(self.bundle)

    def test_saved_build_target_must_be_a_plain_rom_path(self):
        for target in ("../escape/oos168x.sfc", "C:\\Roms\\oos168x.sfc",
                       str(self.root / "engine/Roms/oos168x.sym")):
            with self.subTest(target=target):
                self.saved_build_target(target)
                self.write_native_save()
                with self.assertRaisesRegex(ValueError, "Invalid saved build_target"):
                    verify_bundle(self.bundle)

    def test_native_save_cannot_change_other_build_pins(self):
        for key, value in (("build_script", "python3 /external/build.py"),
                           ("asm_entry_point", "project/Other_main.asm"),
                           ("output_folder", "/external/Roms"),
                           ("git_repository", "/external/source")):
            with self.subTest(key=key):
                self.saved_build_target(self.root / "engine/Roms/gen/oos168x.sfc")
                descriptor = self.bundle / "project.yaze"
                lines = descriptor.read_text().split("\n")
                section = ""
                for index, line in enumerate(lines):
                    if line.startswith("["):
                        section = line
                    elif section == "[build]" and line.startswith(f"{key}="):
                        lines[index] = f"{key}={value}"
                descriptor.write_text("\n".join(lines))
                self.write_native_save()
                with self.assertRaisesRegex(ValueError, f"{key} must equal"):
                    verify_bundle(self.bundle)

    def saved_rom_edit(self):
        """A genuine yaze ROM Save edits the editable bundle `rom` in place."""
        self.capture()
        self.pin_tools()
        self.terrain = self.bundle / self.values()["files", "lyra_terrain_file"]
        self.provenance = {
            name: (self.bundle / name).read_bytes()
            for name in ("authoring-dependencies.json", "manifest.json",
                         "project.yaze", "project/Roms/hack_manifest.json")}
        rom = self.bundle / "rom"
        self.export_rom = rom.read_bytes()
        edited = bytearray(self.export_rom)
        edited[-1] ^= 0xFF
        rom.write_bytes(bytes(edited))

    def test_native_saved_rom_edit_passes_against_frozen_export_provenance(self):
        self.saved_rom_edit()
        self.write_native_save()
        verify_bundle(self.bundle)
        for name, data in self.provenance.items():
            self.assertEqual((self.bundle / name).read_bytes(), data, name)

    def test_external_rom_edit_refuses(self):
        self.saved_rom_edit()
        with self.assertRaisesRegex(
                ValueError, "romChecksum mismatch.*no project.yaze.native-save.json "
                "from a yaze Save binds the edited rom"):
            verify_bundle(self.bundle)
        rom = self.bundle / "rom"
        edited = rom.read_bytes()
        rom.write_bytes(self.export_rom)
        self.write_native_save()
        rom.write_bytes(edited)
        with self.assertRaisesRegex(ValueError, r"current rom \(role rom\)"):
            verify_bundle(self.bundle)

    def test_external_rom_edit_before_project_only_save_refuses(self):
        # yaze binds the ROM only as it loaded or last wrote it: a project-only
        # Save after another writer edits the ROM persists the descriptor but
        # publishes no receipt, so the prior receipt keeps verify refusing.
        self.saved_rom_edit()
        self.write_native_save()
        verify_bundle(self.bundle)
        rom = self.bundle / "rom"
        external = bytearray(rom.read_bytes())
        external[-2] ^= 0xFF
        rom.write_bytes(bytes(external))
        descriptor = self.bundle / "project.yaze"
        saved = descriptor.read_text()
        descriptor.write_text(saved + "# project-only save\n")
        with self.assertRaisesRegex(ValueError, r"current project.yaze \(role project\)"):
            verify_bundle(self.bundle)
        descriptor.write_text(saved)
        with self.assertRaisesRegex(ValueError, r"current rom \(role rom\)"):
            verify_bundle(self.bundle)

    def test_rom_edit_receipt_must_bind_the_editable_rom_not_the_built_rom(self):
        self.saved_rom_edit()
        built = self.bundle / "project/Roms/oos168x.sfc"
        built.write_bytes((self.bundle / "rom").read_bytes())
        self.write_native_save(rom=built)
        with self.assertRaisesRegex(ValueError, r"current rom \(role rom\)"):
            verify_bundle(self.bundle)
        built.unlink()
        self.write_native_save(errors=["rom: explicit incomplete binding"])
        with self.assertRaisesRegex(ValueError, "incomplete Save binding"):
            verify_bundle(self.bundle)

    def test_rom_edit_refuses_blind_manifest_refresh(self):
        self.saved_rom_edit()
        self.write_native_save()
        write_bundle_hack_manifest(self.bundle)
        with self.assertRaisesRegex(ValueError, "export romChecksum|immutable"):
            verify_bundle(self.bundle)
        (self.bundle / "project/Roms/hack_manifest.json").write_bytes(
            self.provenance["project/Roms/hack_manifest.json"])
        manifest = self.bundle / "manifest.json"
        refreshed = json.loads(manifest.read_text())
        refreshed["romChecksum"] = hashlib.sha1(
            (self.bundle / "rom").read_bytes()).hexdigest()
        manifest.write_text(json.dumps(refreshed))
        with self.assertRaises(ValueError):
            verify_bundle(self.bundle)

    def test_authoring_build_guard_survives_bundle_relocation(self):
        from unittest import mock

        self.project.write_text(
            self.project.read_text().replace(
                "lyra_terrain_file=terrain.json", "lyra_terrain_file="
            )
        )
        self.capture()
        relocated = self.root / "moved" / "Renamed.yazeproj"
        relocated.parent.mkdir()
        self.bundle.rename(relocated)
        verify_bundle(relocated)
        with mock.patch.object(
            build_guard.subprocess, "run", return_value=mock.Mock(returncode=0)
        ) as delegate:
            self.assertEqual(
                build_guard.main(["--project", str(relocated / "project.yaze")]), 0
            )
        args, kwargs = delegate.call_args
        self.assertEqual(kwargs["cwd"], relocated)
        self.assertEqual(
            args[0][1], str(relocated / "project/Scripts/Build/build_rom.sh")
        )


if __name__ == "__main__":
    unittest.main()
